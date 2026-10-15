"""Get media duration in seconds from local file or API fields."""

import asyncio
import os
import re


async def duration_from_file(path: str) -> int:
    """Use ffprobe if available, else 0."""
    if not path or not os.path.isfile(path):
        return 0
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode == 0 and out:
            val = float(out.decode().strip())
            return int(val) if val > 0 else 0
    except Exception as e:
        print(f"ffprobe duration fail: {e}")
    return 0


def duration_from_item(item: dict) -> int:
    """Parse duration from API item fields."""
    if not item:
        return 0
    for key in ("duration", "length", "runtime", "time", "lengthSeconds", "duration_seconds"):
        v = item.get(key)
        if v is None:
            continue
        if isinstance(v, (int, float)) and v > 0:
            # if looks like ms
            if v > 10000:
                return int(v / 1000)
            return int(v)
        if isinstance(v, str):
            v = v.strip()
            # "12:34" or "1:02:03"
            m = re.match(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$", v)
            if m:
                h = int(m.group(1) or 0)
                mi = int(m.group(2))
                s = int(m.group(3))
                return h * 3600 + mi * 60 + s
            # plain number string
            try:
                n = float(v)
                if n > 0:
                    return int(n / 1000) if n > 10000 else int(n)
            except Exception:
                pass
    return 0
