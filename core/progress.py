"""
Live progress — Yoru bar + colored buttons
"""

import asyncio
import time
from core.rich_ui import plain_now_playing
from core.buttons import player_keyboard_api, edit_message_styled

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
    build_keyboard_fn=None,
):
    cancel_progress(chat_id)

    if not duration or duration <= 0:
        return

    state = get_state_fn(chat_id)
    state["np_msg_id"] = message.id if hasattr(message, "id") else message.get("message_id")
    state["duration"] = duration
    state["start_ts"] = time.time()
    state["paused_at"] = None
    state["elapsed_base"] = 0
    if "autoplay" not in state:
        state["autoplay"] = False

    msg_id = state["np_msg_id"]

    async def _loop():
        try:
            while True:
                await asyncio.sleep(4)
                st = get_state_fn(chat_id)
                if not st.get("playing"):
                    break
                if st.get("np_msg_id") != msg_id:
                    break

                if st.get("paused"):
                    elapsed = int(st.get("elapsed_base") or 0)
                else:
                    start = st.get("start_ts") or time.time()
                    elapsed = int(st.get("elapsed_base") or 0) + int(time.time() - start)

                elapsed = max(0, min(elapsed, duration))
                qlen = len(st.get("queue") or [])
                title_now = st.get("title") or title
                ap = bool(st.get("autoplay"))

                text = plain_now_playing(
                    title_now, duration, requester,
                    queued=False, queue_len=qlen, pos=elapsed, autoplay=ap,
                )
                kb = player_keyboard_api(paused=bool(st.get("paused")), autoplay=ap)
                await edit_message_styled(chat_id, msg_id, text=text, reply_markup=kb)

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
