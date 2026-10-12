"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ꭙ ᴍᴜꜱɪᴄ ʙᴏᴛ !!

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>
"""

import os
import re
import math
import time
import random
import yt_dlp
import aiohttp
import asyncio
import aiofiles
from config import config
from core.song import Song
from pyrogram import enums
from spotipy import Spotify
from core.groups import get_group
from pyrogram.types import Message
from PIL import Image, ImageDraw, ImageFont
from youtubesearchpython import VideosSearch
from spotipy.oauth2 import SpotifyClientCredentials
from typing import List, Tuple, Optional, AsyncIterator


try:
    sp = Spotify(
        client_credentials_manager=SpotifyClientCredentials(
            config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET
        )
    )
    config.SPOTIFY = True
except BaseException:
    print(
        "WARNING: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET is not set."
        "Bot will work fine but playing songs with spotify playlist won't work."
        "Check your configs or .env file if you want to add them or ask @AsmSupport!"
    )
    config.SPOTIFY = False


themes = [
    "blue",
    "black",
    "red",
    "green",
    "grey",
    "orange",
    "pink",
    "yellow",
]


async def search(message: Message) -> Optional[Song]:
    query = ""
    reply = message.reply_to_message
    if reply:
        if reply.text:
            query = reply.text
        elif reply.media:
            media = reply.audio or reply.video or reply.document
            if not media:
                return None
            lel = await message.reply_text("`Trying To Download...`")
            file = await reply.download(
                progress=progress_bar,
                progress_args=("Downloading...", lel, time.time()),
            )
            await lel.delete()
            return Song(
                {
                    "title": media.file_name or "N/A",
                    "source": reply.link,
                    "remote": file,
                },
                message,
            )
    else:
        query = extract_args(message.text)
    if query == "":
        return None
    is_yt_url, url = check_yt_url(query)
    if is_yt_url:
        return Song(url, message)
    elif config.SPOTIFY and "open.spotify.com/track" in query:
        track_id = query.split("open.spotify.com/track/")[1].split("?")[0]
        track = sp.track(track_id)
        query = f'{" / ".join([artist["name"] for artist in track["artists"]])} - {track["name"]}'
        return Song(query, message)
    else:
        group = get_group(message.chat.id)
        vs = VideosSearch(
            query, limit=1, language=group["lang"], region=group["lang"]
        ).result()
        if len(vs["result"]) > 0 and vs["result"][0]["type"] == "video":
            video = vs["result"][0]
            return Song(video["link"], message)
    return None


def check_yt_url(text: str) -> Tuple[bool, Optional[str]]:
    pattern = re.compile(
        "^((?:https?:)?\\/\\/)?((?:www|m)\\.)?((?:youtube\\.com|youtu.be))(\\/(?:[\\w\\-]+\\?v=|embed\\/|v\\/)?)([\\w\\-]+)([a-zA-Z0-9-_]+)?$"
    )
    matches = re.findall(pattern, text)
    if len(matches) <= 0:
        return False, None

    match = "".join(list(matches[0]))
    return True, match


def extract_args(text: str) -> str:
    if " " not in text:
        return ""
    else:
        return text.split(" ", 1)[1]


async def progress_bar(current, total, ud_type, msg, start):
    now = time.time()
    if total == 0:
        return
    if round((now - start) % 3) == 0 or current == total:
        speed = current / (now - start)
        percentage = current * 100 / total
        time_to_complete = round(((total - current) / speed)) * 1000
        time_to_complete = TimeFormatter(time_to_complete)
        progressbar = "[{0}{1}]".format(
            "".join(["▰" for i in range(math.floor(percentage / 10))]),
            "".join(["▱" for i in range(10 - math.floor(percentage / 10))]),
        )
        current_message = f"**{ud_type}** `{round(percentage, 2)}%`\n`{progressbar}`\n**Done**: `{humanbytes(current)}` | **Total**: `{humanbytes(total)}`\n**Speed**: `{humanbytes(speed)}/s` | **ETA**: `{time_to_complete}`"
        if msg:
            try:
                await msg.edit(text=current_message)
            except BaseException:
                pass


def humanbytes(size: int) -> str:
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: " ", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + "B"


async def delete_messages(messages: List[Message]):
    await asyncio.sleep(10)
    for msg in messages:
        if msg.chat.type == enums.ChatType.SUPERGROUP:
            try:
                await msg.delete()
            except BaseException:
                pass


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + " Days, ") if days else "")
        + ((str(hours) + " Hours, ") if hours else "")
        + ((str(minutes) + " Min, ") if minutes else "")
        + ((str(seconds) + " Sec, ") if seconds else "")
        + ((str(milliseconds) + " MS, ") if milliseconds else "")
    )
    return tmp[:-2]


def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage


async def generate_cover(title, ctitle, chatid, thumbnail):
    async with aiohttp.ClientSession() as session:
        async with session.get(thumbnail) as resp:
            if resp.status == 200:
                f = await aiofiles.open(f"thumb{chatid}.png", mode="wb")
                await f.write(await resp.read())
                await f.close()

    theme = random.choice(themes)
    ctitle = await special_to_normal(ctitle)
    image1 = Image.open(f"thumb{chatid}.png")
    image2 = Image.open(f"theme/{theme}.PNG")
    image3 = changeImageSize(1280, 720, image1)
    image4 = changeImageSize(1280, 720, image2)
    image5 = image3.convert("RGBA")
    image6 = image4.convert("RGBA")
    Image.alpha_composite(image5, image6).save(f"temp{chatid}.png")
    img = Image.open(f"temp{chatid}.png")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("theme/font.ttf", 85)
    font2 = ImageFont.truetype("theme/font.ttf", 60)
    draw.text(
        (20, 45),
        f"Playing on: {ctitle[:14]}...",
        fill="white",
        stroke_width=1,
        stroke_fill="white",
        font=font2,
    )
    draw.text(
        (25, 595),
        f"{title[:27]}...",
        fill="white",
        stroke_width=2,
        stroke_fill="white",
        font=font,
    )
    img.save(f"final{chatid}.png")
    os.remove(f"temp{chatid}.png")
    os.remove(f"thumb{chatid}.png")
    final = f"final{chatid}.png"
    return final


async def special_to_normal(ctitle):
    string = ctitle
    font1 = list("𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ")
    font2 = list("𝕬𝕭𝕮𝕯𝕰𝕱𝕲𝕳𝕴𝕵𝕶𝕷𝕸𝕹𝕺𝕻𝕼𝕽𝕾𝕿𝖀𝖁𝖂𝖃𝖄𝖅")
    font3 = list("𝓐𝓑𝓒𝓓𝓔𝓕𝓖𝓗𝓘𝓙𝓚𝓛𝓜𝓝𝓞𝓟𝓠𝓡𝓢𝓣𝓤𝓥𝓦𝓧𝓨𝓩")
    font4 = list("𝒜𝐵𝒞𝒟𝐸𝐹𝒢𝐻𝐼𝒥𝒦𝐿𝑀𝒩𝒪𝒫𝒬𝑅𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵")
    font5 = list("𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ")
    font6 = list("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ")
    font26 = list("𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙")
    font27 = list("𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭")
    font28 = list("𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡")
    font29 = list("𝘼𝘽𝘾𝘿𝙀𝙁𝙂𝙃𝙄𝙅𝙆𝙇𝙈𝙉𝙊𝙋𝙌𝙍𝙎𝙏𝙐𝙑𝙒𝙓𝙔𝙕")
    font30 = list("𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉")
    font1L = list("𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷")
    font2L = list("𝖆𝖇𝖈𝖉𝖊𝖋𝖌𝖍𝖎𝖏𝖐𝖑𝖒𝖓𝖔𝖕𝖖𝖗𝖘𝖙𝖚𝖛𝖜𝖝𝖞𝖟")
    font3L = list("𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃")
    font4L = list("𝒶𝒷𝒸𝒹𝑒𝒻𝑔𝒽𝒾𝒿𝓀𝓁𝓂𝓃𝑜𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏")
    font5L = list("𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫")
    font6L = list("ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ")
    font27L = list("𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳")
    font28L = list("𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇")
    font29L = list("𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻")
    font30L = list("𝙖𝙗𝙘𝙙𝙚𝙛𝙜𝙝𝙞𝙟𝙠𝙡𝙢𝙣𝙤𝙥𝙦𝙧𝙨𝙩𝙪𝙫𝙬𝙭𝙮𝙯")
    font31L = list("𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣")
    normal = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    normalL = list("abcdefghijklmnopqrstuvwxyz")
    cout = 0
    for XCB in font1:
        string = string.replace(font1[cout], normal[cout])
        string = string.replace(font2[cout], normal[cout])
        string = string.replace(font3[cout], normal[cout])
        string = string.replace(font4[cout], normal[cout])
        string = string.replace(font5[cout], normal[cout])
        string = string.replace(font6[cout], normal[cout])
        string = string.replace(font26[cout], normal[cout])
        string = string.replace(font27[cout], normal[cout])
        string = string.replace(font28[cout], normal[cout])
        string = string.replace(font29[cout], normal[cout])
        string = string.replace(font30[cout], normal[cout])
        string = string.replace(font1L[cout], normalL[cout])
        string = string.replace(font2L[cout], normalL[cout])
        string = string.replace(font3L[cout], normalL[cout])
        string = string.replace(font4L[cout], normalL[cout])
        string = string.replace(font5L[cout], normalL[cout])
        string = string.replace(font6L[cout], normalL[cout])
        string = string.replace(font27L[cout], normalL[cout])
        string = string.replace(font28L[cout], normalL[cout])
        string = string.replace(font29L[cout], normalL[cout])
        string = string.replace(font30L[cout], normalL[cout])
        string = string.replace(font31L[cout], normalL[cout])
        cout += 1
    return string


async def get_youtube_playlist(pl_url: str, message: Message) -> AsyncIterator[Song]:
    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'ignoreerrors': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(pl_url, download=False)
        
    if info and 'entries' in info:
        for entry in info['entries']:
            if entry and entry.get('url'):
                song = Song(entry['url'], message)
                song.title = entry.get('title', 'Unknown Title')
                yield song


async def get_spotify_playlist(pl_url: str, message: Message) -> AsyncIterator[Song]:
    pl_id = re.split("[^a-zA-Z0-9]", pl_url.split("spotify.com/playlist/")[1])[0]
    offset = 0
    while True:
        resp = sp.playlist_items(
            pl_id, fields="items.track.name,items.track.artists.name", offset=offset
        )
        if len(resp["items"]) == 0:
            break
        for item in resp["items"]:
            track = item["track"]
            song_name = f'{",".join([artist["name"] for artist in track["artists"]])} - {track["name"]}'
            vs = VideosSearch(song_name, limit=1).result()
            if len(vs["result"]) > 0 and vs["result"][0]["type"] == "video":
                video = vs["result"][0]
                song = Song(video["link"], message)
                song.title = video["title"]
                yield song
        offset += len(resp["items"])
