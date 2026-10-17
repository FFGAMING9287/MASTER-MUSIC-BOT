"""
Now Playing UI — Yoru-style layout (FFGAMING credits only)
"""

import re
import aiohttp
from config import config


def fmt_duration(sec):
    if not sec:
        return "00:00"
    try:
        sec = int(sec)
    except Exception:
        return "00:00"
    m, s = divmod(max(0, sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def clean_name(text: str) -> str:
    if not text:
        return "User"
    text = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.strip()
    return text[:60] if text else "User"


def progress_bar(duration: int, pos: int = 0) -> str:
    """Yoru-style: 01:30 |-------♪|- 00:03  (elapsed | bar | remaining)"""
    total = max(int(duration or 0), 1)
    pos = max(0, min(int(pos or 0), total))
    remain = max(0, total - pos)
    width = 12
    filled = int((pos / total) * width) if total else 0
    filled = min(filled, width - 1)
    bar = "-" * filled + "♪" + "-" * max(0, width - filled - 1)
    return f"{fmt_duration(pos)} |{bar}|- {fmt_duration(remain)}"


def _kb_to_api(keyboard):
    if not keyboard:
        return None
    rows = []
    for row in keyboard.inline_keyboard:
        r = []
        for btn in row:
            item = {"text": btn.text}
            if getattr(btn, "callback_data", None):
                item["callback_data"] = btn.callback_data
            if getattr(btn, "url", None):
                item["url"] = btn.url
            style = getattr(btn, "style", None)
            if style:
                item["style"] = style
            r.append(item)
        rows.append(r)
    return {"inline_keyboard": rows}


async def send_rich(chat_id, html: str, reply_markup=None):
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/sendRichMessage"
    payload = {"chat_id": chat_id, "rich_message": {"html": html}}
    api_kb = _kb_to_api(reply_markup)
    if api_kb:
        payload["reply_markup"] = api_kb
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return True
                print(f"sendRichMessage fail: {data}")
                return False
    except Exception as e:
        print(f"sendRichMessage error: {e}")
        return False


def plain_now_playing(title, duration=0, requester="User", queued=False, queue_len=0, pos=0, autoplay=False):
    title = clean_name(title)[:55]
    requester = clean_name(requester)
    dur = fmt_duration(duration)

    if queued:
        return (
            f"🎧 **ADDED TO QUEUE**\n\n"
            f"🎵 **TITLE :** `{title}`\n"
            f"⏱ **LENGTH :** `{dur} MINS`\n"
            f"👤 **REQUESTER :** {requester}"
        )

    bar = progress_bar(duration, pos)
    ap = "ON" if autoplay else "OFF"
    return (
        f"🎬 **STREAM HAS STARTED. ENJOY THE MUSIC |**\n\n"
        f"🎵 **TITLE :** `{title}`\n"
        f"⏱ **LENGTH :** `{dur} MINS`\n"
        f"👤 **REQUESTER :** {requester}\n\n"
        f"`{bar}`"
    )


def html_now_playing(title, duration=0, requester="User", queued=False, thumb="", pos=0, autoplay=False) -> str:
    title = clean_name(title)[:70]
    requester = clean_name(requester)
    dur = fmt_duration(duration)
    bar = progress_bar(duration, pos)
    ap = "ON" if autoplay else "OFF"

    media = ""
    if thumb and str(thumb).startswith("http"):
        media = f'<tg-slideshow><img src="{thumb}"/><figcaption>{title}</figcaption></tg-slideshow>'

    if queued:
        return f"""
<h3>🎧 Added To Queue</h3>
{media}
<p>🎵 <b>TITLE :</b> {title}<br/>
⏱ <b>LENGTH :</b> <code>{dur} MINS</code><br/>
👤 <b>REQUESTER :</b> {requester}</p>
""".strip()

    return f"""
<h3>🎬 STREAM HAS STARTED. ENJOY THE MUSIC |</h3>
{media}
<p>🎵 <b>TITLE :</b> {title}<br/>
⏱ <b>LENGTH :</b> <code>{dur} MINS</code><br/>
👤 <b>REQUESTER :</b> {requester}</p>
<blockquote><code>{bar}</code></blockquote>
""".strip()


def html_start(name: str, mode: str) -> str:
    return f"""
<h2>🎧 FFGAMING X MUSIC BOT</h2>
<p>Welcome <b>{name}</b> ✨</p>
<hr/>
<table>
<tr><td>Mode</td><td>{mode}</td></tr>
<tr><td>Status</td><td>Online ✅</td></tr>
</table>
<hr/>
<p>🎵 <code>/song</code> <code>/yt</code> · 🎬 <code>/play</code> <code>/movie</code><br/>
🔞 <code>/adult</code> · ⏯ <code>/skip</code> <code>/pause</code> <code>/stop</code></p>
<blockquote>😌 Sit back, relax &amp; enjoy</blockquote>
<tg-button-row>
  <tg-button type="callback_data" data="help|song" style="primary">🎵 Song</tg-button>
  <tg-button type="callback_data" data="help|movie" style="success">🎬 Movie</tg-button>
  <tg-button type="callback_data" data="help|adult" style="danger">🔞 Adult</tg-button>
</tg-button-row>
""".strip()


def html_help(mode: str) -> str:
    return f"""
<h2>📖 Command Guide</h2>
<p>Mode : <code>{mode}</code></p>
<hr/>
<table>
<tr><td>🎵 YouTube</td><td><code>/song</code> <code>/yt</code></td></tr>
<tr><td>🎬 Movies</td><td><code>/play</code> <code>/movie</code></td></tr>
<tr><td>🔞 Adult</td><td><code>/adult</code> <code>/xxx</code></td></tr>
<tr><td>⏯ Controls</td><td><code>/skip</code> <code>/pause</code> <code>/stop</code></td></tr>
</table>
""".strip()


def html_search(kind: str, query: str = "", count: int = 0) -> str:
    icons = {"YouTube": "🎵", "Adult": "🔞", "Movie": "🎬", "generic": "🔍"}
    icon = icons.get(kind, "🔍")
    if count:
        return f"""
<h3>{icon} {kind} Results</h3>
<hr/>
<table>
<tr><td>Query</td><td><code>{clean_name(query)}</code></td></tr>
<tr><td>Found</td><td><b>{count}</b></td></tr>
</table>
<blockquote>👇 Choose one from the buttons below</blockquote>
""".strip()
    return f"<h3>{icon} Searching {kind}...</h3><p>⏳ Please wait</p>"


def html_download(title: str, quality: str = "") -> str:
    q = f"<tr><td>Quality</td><td><code>{quality}</code></td></tr>" if quality else ""
    return f"""
<h3>⬇️ Downloading</h3>
<hr/>
<table>
<tr><td>Title</td><td>{clean_name(title)[:55]}</td></tr>
{q}
</table>
<blockquote>⏳ Please wait...</blockquote>
""".strip()


def html_queue(body: str) -> str:
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    return f"<h3>☰ Queue</h3><hr/><p>{safe}</p>"


def html_ping() -> str:
    return "<h3>🤖 Pong!</h3><p>✅ Online · 🎧 Ready</p>"


def html_mode(status: str, detail: str = "") -> str:
    return f"<h3>🔐 Mode</h3><p><code>{status}</code></p><p>{detail}</p>"


def html_error(msg: str) -> str:
    return f"<h3>❌ Error</h3><p>{clean_name(msg)[:200]}</p>"


def html_info(title: str, body: str) -> str:
    return f"<h3>{title}</h3><hr/><p>{body}</p>"


def status_searching(kind="YouTube"):
    return f"🔍 **Searching {kind}...**\n\n⏳ Please wait"


def status_downloading(title, quality=""):
    q = f"\n📦 `{quality}`" if quality else ""
    return f"⬇️ **Downloading**\n\n`{clean_name(title)[:50]}`{q}\n\n⏳ Please wait"


def status_results(kind, query, count):
    return f"{kind} **Results**\n\n🔎 `{query}`\n📊 **{count}**\n\n👇 Choose"
