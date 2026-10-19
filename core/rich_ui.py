"""
Now Playing UI — Yoru-style layout (FFGAMING credits only)
Progress lives on the blue keyboard button (NOÉ style).
Start/Help: full menu UI restored.
"""

import html
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
    text = text.replace("&", "&").replace("<", "<").replace(">", ">")
    text = text.strip()
    return text[:60] if text else "User"


def progress_bar(duration: int, pos: int = 0) -> str:
    total = max(int(duration or 0), 1)
    pos = max(0, min(int(pos or 0), total))
    width = 14
    filled = int((pos / total) * width) if total else 0
    filled = min(max(filled, 0), width - 1)
    bar = "-" * filled + "♪" + "-" * max(0, width - filled - 1)
    return f"{fmt_duration(pos)}  {bar}  {fmt_duration(total)}"


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
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return True
                print(f"sendRichMessage fail: {data}")
                return False
    except Exception as e:
        print(f"send_rich error: {e}")
        return False


def plain_now_playing(
    title,
    duration=0,
    requester="User",
    queued=False,
    queue_len=0,
    pos=0,
    autoplay=False,
):
    """HTML caption for the artwork card; progress and controls are buttons."""
    title = html.escape(clean_name(title)[:70])
    requester = html.escape(clean_name(requester))
    dur = fmt_duration(duration)

    if queued:
        return (
            f"🎧 <b>Added to Queue · #{queue_len}</b>\n\n"
            f"🎵 <b>Title:</b> <i>{title}</i>\n"
            f"⏱ <b>Track Duration:</b> {dur}\n"
            f"👤 <b>Requested By:</b> {requester}"
        )

    return (
        "🎧 <b>Music Is Playing</b>\n\n"
        f"🎵 <b>Now Playing:</b> <i>{title}</i>\n"
        f"⏱ <b>Track Duration:</b> {dur}\n"
        f"👤 <b>Requested By:</b> {requester}\n\n"
        "🎼 <b>Your Track Is Now Playing</b>\n"
        "🌿 Sit back, relax &amp; enjoy the music"
    )


def html_now_playing(
    title, duration=0, requester="User", queued=False, thumb="", pos=0, autoplay=False
) -> str:
    title = clean_name(title)[:70]
    requester = clean_name(requester)
    dur = fmt_duration(duration)

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
<h3>| Started streaming</h3>
{media}
<p><b>Title:</b> {title}<br/>
<b>Duration:</b> {dur} min<br/>
<b>Requested by:</b> {requester}</p>
""".strip()


def html_start(name: str, mode: str) -> str:
    name = clean_name(name)
    return f"""
<h2>🎧 FFGAMING X MUSIC BOT</h2>
<p>Welcome to <b>FFGAMING X MUSIC</b>, {name} ✨</p>
<hr/>
<p>📋 <b>Bot Information</b></p>
<table>
<tr><td>Mode</td><td>{mode}</td></tr>
<tr><td>Status</td><td>Online ✅</td></tr>
<tr><td>Voice Chat</td><td>Supported</td></tr>
</table>
<hr/>
<p>🎵 <b>Features</b></p>
<table>
<tr><td>Music</td><td><code>/song</code> <code>/yt</code></td></tr>
<tr><td>Movies</td><td><code>/play</code> <code>/movie</code></td></tr>
<tr><td>Adult</td><td><code>/adult</code> <code>/xxx</code></td></tr>
<tr><td>Controls</td><td><code>/skip</code> <code>/pause</code> <code>/stop</code></td></tr>
<tr><td>Owner</td><td><code>/mode public|private</code></td></tr>
</table>
<blockquote>😌 Sit back, relax & enjoy the music</blockquote>
<p>↑ Select a menu below to continue</p>
""".strip()


def html_help(mode: str) -> str:
    return f"""
<h2>🎧 FFGAMING X MUSIC BOT</h2>
<p>👋 Hello!</p>
<p>🔐 Mode : {mode}</p>
<hr/>
<p>🎵 <b>Music</b> — <code>/song</code> <code>/yt</code></p>
<p>🎬 <b>Movies</b> — <code>/play</code> <code>/movie</code></p>
<p>🔞 <b>Adult</b> — <code>/adult</code> <code>/xxx</code></p>
<p>⏯ <b>Controls</b> — <code>/skip</code> <code>/pause</code> <code>/resume</code> <code>/stop</code> <code>/queue</code></p>
<p>🔐 <b>Owner</b> — <code>/mode public|private</code></p>
<hr/>
<blockquote>😌 Sit back, relax & enjoy the music</blockquote>
""".strip()


def html_search(kind: str, query: str = "", count: int = 0) -> str:
    icon = "🎵" if kind.lower() in ("youtube", "song") else "🎬"
    if query and count:
        return f"""
<h3>{icon} {kind} Results</h3>
<hr/>
<table>
<tr><td>Query</td><td><code>{clean_name(query)[:40]}</code></td></tr>
<tr><td>Found</td><td><b>{count}</b></td></tr>
</table>
<blockquote>👇 Choose one from the buttons below</blockquote>
""".strip()
    return f"<h3>{icon} Searching {kind}...</h3>"


def html_download(title: str, quality: str = "") -> str:
    return "<p>🔍 Searching and downloading...</p>"


def html_queue(body: str) -> str:
    safe = (
        body.replace("&", "&")
        .replace("<", "<")
        .replace(">", ">")
        .replace("\n", "<br/>")
    )
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
    return f"🔍 Searching {kind}...\n\n⏳ Please wait."


def status_downloading(title, quality=""):
    label = clean_name(title)[:55]
    detail = f"\nQuality: {clean_name(quality)[:20]}" if quality else ""
    return f"⬇️ Preparing {label}...{detail}\n\n⏳ Please wait."


def status_results(kind, query, count):
    icon = {"YouTube": "🎵", "Movie": "🎬", "Adult": "🔞"}.get(kind, "🔎")
    return (
        f"{icon} {kind} Results\n\n🔎 {clean_name(query)[:70]}\n"
        f"📊 Found: {count}\n👇 Choose a result below"
    )
