"""
Live progress bar — edits same Now Playing message every few seconds.
"""

import asyncio
import time
from core.rich_ui import plain_now_playing

_tasks = {}


def cancel_progress(chat_id: int):
    t = _tasks.pop(chat_id, None)
    if t and not t.done():
        t.cancel()


async def start_progress(
    client,
    chat_id: int,
    message,
    title: str,
    duration: int,
    requester: str,
    get_state_fn,
    build_keyboard_fn,
):
    cancel_progress(chat_id)

    if not duration or duration <= 0:
        return

    state = get_state_fn(chat_id)
    state["np_msg_id"] = message.id
    state["duration"] = duration
    state["start_ts"] = time.time()
    state["paused_at"] = None
    state["elapsed_base"] = 0

    async def _loop():
        try:
            while True:
                await asyncio.sleep(4)
                st = get_state_fn(chat_id)
                if not st.get("playing"):
                    break
                if st.get("np_msg_id") != message.id:
                    break

                if st.get("paused"):
                    elapsed = int(st.get("elapsed_base") or 0)
                else:
                    start = st.get("start_ts") or time.time()
                    elapsed = int(st.get("elapsed_base") or 0) + int(time.time() - start)

                elapsed = max(0, min(elapsed, duration))
                qlen = len(st.get("queue") or [])
                title_now = st.get("title") or title

                text = plain_now_playing(
                    title_now, duration, requester,
                    queued=False, queue_len=qlen, pos=elapsed,
                )
                kb = build_keyboard_fn(paused=bool(st.get("paused")), queue_len=qlen)
                try:
                    if getattr(message, "photo", None):
                        await message.edit_caption(text, reply_markup=kb)
                    else:
                        await message.edit_text(text, reply_markup=kb)
                except Exception as e:
                    err = str(e).lower()
                    if "message is not modified" in err:
                        continue
                    if "message to edit not found" in err or "message_id_invalid" in err:
                        break
                    print(f"progress edit: {e}")

                if elapsed >= duration:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"progress loop error: {e}")
        finally:
            _tasks.pop(chat_id, None)

    _tasks[chat_id] = asyncio.create_task(_loop())


def on_pause(chat_id: int, get_state_fn):
    st = get_state_fn(chat_id)
    if st.get("paused"):
        return
    start = st.get("start_ts") or time.time()
    st["elapsed_base"] = int(st.get("elapsed_base") or 0) + int(time.time() - start)
    st["paused_at"] = time.time()


def on_resume(chat_id: int, get_state_fn):
    st = get_state_fn(chat_id)
    st["start_ts"] = time.time()
    st["paused_at"] = None
