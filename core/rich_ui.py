"""
Premium Now Playing + helper text styles
"""

import re


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
    total = max(int(duration or 0), 1)
    pos = max(0, min(int(pos or 0), total))
    width = 16
    filled = int((pos / total) * width)
    # fancy bar
    bar = "█" * filled + "●" + "░" * max(0, width - filled)
    return f"`{fmt_duration(pos)}`  {bar}  `{fmt_duration(total)}`"


def plain_now_playing(title, duration=0, requester="User", queued=False, queue_len=0, pos=0):
    title = clean_name(title)[:55]
    requester = clean_name(requester)
    dur = fmt_duration(duration)

    if queued:
        return (
            f"╔══════════════════════╗\n"
            f"║  🎧  **ADDED TO QUEUE**\n"
            f"╚══════════════════════╝\n\n"
            f"🎵 **Track**\n`{title}`\n\n"
            f"⏱ **Duration**  `{dur} MIN`\n"
            f"👤 **By**  {requester}\n"
            f"☰ **Position**  #{queue_len or 1}"
        )

    bar = progress_bar(duration, pos)
    return (
        f"╔══════════════════════╗\n"
        f"║  🎧  **MUSIC IS PLAYING**\n"
        f"╚══════════════════════╝\n\n"
        f"🎵 **Now Playing**\n`{title}`\n\n"
        f"⏱ **Duration**  `{dur} MIN`\n"
        f"👤 **Requested By**  {requester}\n\n"
        f"{bar}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎶 Your track is now playing\n"
        f"😌 Sit back, relax & enjoy"
    )


def status_searching(kind="YouTube"):
    icons = {"YouTube": "🎵", "movie": "🎬", "adult": "🔞", "generic": "🔍"}
    icon = icons.get(kind, "🔍")
    return f"{icon} **Searching {kind}...**\n\n⏳ Please wait a moment"


def status_downloading(title, quality=""):
    q = f"\n📦 Quality : `{quality}`" if quality else ""
    return (
        f"⬇️ **Downloading**\n\n"
        f"`{clean_name(title)[:50]}`{q}\n\n"
        f"⏳ This may take a while..."
    )


def status_results(kind, query, count):
    icons = {"YouTube": "🎵", "Adult": "🔞", "Movie": "🎬"}
    icon = icons.get(kind, "🔍")
    return (
        f"{icon} **{kind} Results**\n\n"
        f"🔎 Query : `{query}`\n"
        f"📊 Found : **{count}**\n\n"
        f"👇 Choose one below"
    )
