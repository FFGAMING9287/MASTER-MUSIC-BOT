"""
Music Player + Movie Search + URL Stream, Telegram Voice Chat Bot
Integrated version with movie-downloader API and Render URL Streaming support
"""

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import os
import json
import shutil
import requests
from config import config
from core.song import Song
from pyrogram.types import Message
from pytgcalls import filters as fl
from pyrogram import Client, filters
from pytgcalls.types import Update, ChatUpdate
from pytgcalls.types.stream import StreamEnded
from core.decorators import language, register, only_admins, handle_error
from pytgcalls.exceptions import (
    NotInCallError, NoActiveGroupCall)
from core import (
    app, ytdl, safone, search, is_sudo, is_admin, get_group, get_queue,
    pytgcalls, set_group, set_title, all_groups, clear_queue, check_yt_url,
    extract_args, start_stream, shuffle_queue, delete_messages,
    get_spotify_playlist, get_youtube_playlist)
from movie_handler import MovieAPI, search_movie, create_movie_keyboard

REPO = """
🤖 **Music Player + Movie Search**

- Repo: [GitHub](https://github.com/FFGAMING9287/MUSICBOT.git)
- License: AGPL-3.0-or-later
- Features: Music + Movies via API + URL Stream
"""

if config.BOT_TOKEN:
    bot = Client(
        "MusicPlayer",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True,
    )
    client = bot
else:
    client = app


@client.on_message(filters.command("repo", config.PREFIXES) & ~filters.bot)
@handle_error
async def repo(_, message: Message):
    await message.reply_text(REPO, disable_web_page_preview=True)


@client.on_message(filters.command("ping", config.PREFIXES) & ~filters.bot)
@handle_error
async def ping(_, message: Message):
    await message.reply_text(f"🤖 **Pong!**\n`{pytgcalls.ping} ms`")


@client.on_message(filters.command("start", config.PREFIXES) & ~filters.bot)
@language
@handle_error
async def start(_, message: Message, lang):
    await message.reply_text(lang["startText"] % message.from_user.mention)


@client.on_message(filters.command("help", config.PREFIXES) & ~filters.bot)
@language
@handle_error
async def help(_, message: Message, lang):
    help_text = lang["helpText"].replace("<prefix>", config.PREFIXES[0])
    help_text += f"\n\n**Movie Commands:**\n`{config.PREFIXES[0]}movie <title>` - Search for movies\n`{config.PREFIXES[0]}playurl <link>` - Stream video via URL"
    await message.reply_text(help_text)


# ================== MOVIE SEARCH COMMAND ==================

@client.on_message(filters.command(["movie", "m"], config.PREFIXES) & ~filters.private)
@register
@language
@handle_error
async def search_movie_command(_, message: Message, lang):
    """
    Search for movies using the movie-downloader API
    
    Usage: /movie Fairy Tail
    """
    chat_id = message.chat.id
    
    # Extract movie title from command
    query = extract_args(message.text)
    
    if not query or query.strip() == "":
        k = await message.reply_text("🎬 **Movie Search**\n\nUsage: `/movie <movie title>`\n\nExample: `/movie Fairy Tail`")
        await delete_messages([message, k])
        return
    
    # Show searching indicator
    searching = await message.reply_text(f"🔍 Searching for `{query}`...")
    
    try:
        # Call the movie API
        results = await MovieAPI.search(query.strip())
        
        if not results or len(results) == 0:
            await searching.edit_text(f"❌ No movies found for `{query}`")
            await delete_messages([message, searching])
            return
        
        # Format results
        formatted_results = "🎬 **Movie Search Results:**\n\n"
        
        for i, movie in enumerate(results[:5], 1):
            title = movie.get("title", "N/A")
            year = movie.get("year", "")
            imdb_id = movie.get("imdbID", "")
            plot = movie.get("plot", "")
            rating = movie.get("imdbRating", "N/A")
            
            year_str = f" ({year})" if year else ""
            plot_str = f"\n📝 {plot[:100]}..." if plot and len(plot) > 0 else ""
            rating_str = f"\n⭐ Rating: {rating}" if rating and rating != "N/A" else ""
            
            imdb_link = f"[View on IMDb](https://imdb.com/title/{imdb_id})" if imdb_id else ""
            
            formatted_results += f"**{i}. {title}**{year_str}\n"
            if imdb_link:
                formatted_results += f"{imdb_link}\n"
            formatted_results += f"{rating_str}{plot_str}\n\n"
        
        # Send results with keyboard
        keyboard = create_movie_keyboard(results)
        await searching.edit_text(
            formatted_results,
            disable_web_page_preview=True,
            reply_markup=keyboard
        )
        
        await delete_messages([message])
        
    except Exception as e:
        await searching.edit_text(f"❌ Error searching movies: `{str(e)}`")
        await delete_messages([message, searching])


# ================== URL / VIDEO STREAM COMMAND ==================

@client.on_message(filters.command(["playurl", "vstream"], config.PREFIXES) & ~filters.private)
@register
@language
@handle_error
async def play_url_video(_, message: Message, lang):
    if len(message.command) < 2:
        k = await message.reply_text("Bhai, koi video link toh do! Jaise: `/playurl <link>`")
        return await delete_messages([message, k])
    
    target_url = message.text.split(None, 1)[1]
    msg = await message.reply_text("🔄 `Submitting link to server...`")

    try:
        # Step 1: Task Add karo Render API par
        api_base = "https://fvz.onrender.com"
        add_res = requests.post(f"{api_base}/api/add", json={"url": target_url}, timeout=15).json()
        task_id = add_res.get("task_id")
        
        if not task_id:
            return await msg.edit_text("❌ Server par task submit nahi ho paya.")

        # Step 2: Task Status Poll karo jab tak complete na ho
        await msg.edit_text("⏳ `Processing video stream on server...`")
        data = None
        
        for _ in range(30): # Max 30 attempts (~60 seconds)
            await asyncio.sleep(2)
            status_res = requests.get(f"{api_base}/api/status/{task_id}", timeout=10).json()
            status = status_res.get("status")
            
            if status == "completed":
                data = status_res
                break
            elif status == "failed":
                return await msg.edit_text(f"❌ Processing Failed: {status_res.get('error', 'Unknown error')}")

        if not data:
            return await msg.edit_text("⏱️️ Request timed out. Server response slow tha.")

        # Step 3: Direct Link ya File URL nikaalo
        direct_link = data.get("direct_link")
        files = data.get("files", [])
        
        stream_url = direct_link
        if not stream_url and len(files) > 0:
            stream_url = files[0].get("link")
            
        if not stream_url:
            return await msg.edit_text("❌ Server se koi playable stream link nahi mila.")

        title = data.get("title", "Universal Media Stream")
        thumb = data.get("thumbnail") or "https://telegra.ph/file/820cac7cb7b1a025542e2.jpg"

        # Step 4: Song class bana kar Voice Chat mein stream karo
        song_dict = {
            "title": title,
            "duration": "N/A",
            "thumb": thumb,
            "remote": stream_url,
            "source": target_url,
        }
        
        song = Song(song_dict, message)
        chat_id = message.chat.id
        group = get_group(chat_id)

        if not group["is_playing"]:
            set_group(chat_id, is_playing=True, now_playing=song)
            await msg.edit_text(f"✅ **{title}** ready hai!\n🚀 Voice chat mein stream start ho rahi hai...")
            await start_stream(song, lang)
            await delete_messages([message])
        else:
            queue = get_queue(chat_id)
            await queue.put(song)
            await msg.edit_text(f"✅ **{title}** queue mein add kar di gayi hai! (Position: {len(queue)})")
            await delete_messages([message])

    except Exception as e:
        await msg.edit_text(f"❌ Error aa gaya: `{str(e)}`")


# ================== ORIGINAL MUSIC COMMANDS ==================

@client.on_message(filters.command(["p", "play"], config.PREFIXES) & ~filters.private)
@register
@language
@handle_error
async def play_stream(_, message: Message, lang):
    chat_id = message.chat.id
    group = get_group(chat_id)
    if group["admins_only"]:
        check = await is_admin(message)
        if not check:
            k = await message.reply_text(lang["notAllowed"])
            return await delete_messages([message, k])
    song = await search(message)
    if song is None:
        k = await message.reply_text(lang["notFound"])
        return await delete_messages([message, k])
    ok, status = await song.parse()
    if not ok:
        raise Exception(status)
    if not group["is_playing"]:
        set_group(chat_id, is_playing=True, now_playing=song)
        await start_stream(song, lang)
        await delete_messages([message])
    else:
        queue = get_queue(chat_id)
        await queue.put(song)
        k = await message.reply_text(
            lang["addedToQueue"] % (song.title, song.source, len(queue)),
            disable_web_page_preview=True,
        )
        await delete_messages([message, k])


@client.on_message(
    filters.command(["radio", "stream"], config.PREFIXES) & ~filters.private
)
@register
@language
@handle_error
async def live_stream(_, message: Message, lang):
    chat_id = message.chat.id
    group = get_group(chat_id)
    if group["admins_only"]:
        check = await is_admin(message)
        if not check:
            k = await message.reply_text(lang["notAllowed"])
            return await delete_messages([message, k])
    args = extract_args(message.text)
    if args is None:
        k = await message.reply_text(lang["notFound"])
        return await delete_messages([message, k])
    if " " in args and args.count(" ") == 1 and args[-5:] == "parse":
        song = Song({"source": args.split(" ")[0], "parsed": False}, message)
    else:
        is_yt_url, url = check_yt_url(args)
        if is_yt_url:
            meta = ytdl.extract_info(url, download=False)
            formats = meta.get("formats", [meta])
            for f in formats:
                ytstreamlink = f["url"]
            link = ytstreamlink
            song = Song(
                {"title": "YouTube Stream", "source": link, "remote": link}, message
            )
        else:
            song = Song(
                {"title": "Live Stream", "source": args, "remote": args}, message
            )
    ok, status = await song.parse()
    if not ok:
        raise Exception(status)
    if not group["is_playing"]:
        set_group(chat_id, is_playing=True, now_playing=song)
        await start_stream(song, lang)
        await delete_messages([message])
    else:
        queue = get_queue(chat_id)
        await queue.put(song)
        k = await message.reply_text(
            lang["addedToQueue"] % (song.title, song.source, len(queue)),
            disable_web_page_preview=True,
        )
        await delete_messages([message, k])


@client.on_message(
    filters.command(["skip", "next"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def skip_track(_, message: Message, lang):
    chat_id = message.chat.id
    group = get_group(chat_id)
    if group["loop"]:
        await start_stream(group["now_playing"], lang)
    else:
        queue = get_queue(chat_id)
        if len(queue) > 0:
            next_song = await queue.get()
            if not next_song.parsed:
                ok, status = await next_song.parse()
                if not ok:
                    raise Exception(status)
            set_group(chat_id, now_playing=next_song)
            await start_stream(next_song, lang)
            await delete_messages([message])
        else:
            set_group(chat_id, is_playing=False, now_playing=None)
            await set_title(message, "")
            try:
                await pytgcalls.leave_call(chat_id)
                k = await message.reply_text(lang["queueEmpty"])
            except (NoActiveGroupCall, NotInCallError):
                k = await message.reply_text(lang["notActive"])
            await delete_messages([message, k])


@client.on_message(filters.command(["m", "mute"], config.PREFIXES) & ~filters.private)
@register
@language
@only_admins
@handle_error
async def mute_vc(_, message: Message, lang):
    chat_id = message.chat.id
    try:
        await pytgcalls.mute_stream(chat_id)
        k = await message.reply_text(lang["muted"])
    except (NoActiveGroupCall, NotInCallError):
        k = await message.reply_text(lang["notActive"])
    await delete_messages([message, k])


@client.on_message(
    filters.command(["um", "unmute"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def unmute_vc(_, message: Message, lang):
    chat_id = message.chat.id
    try:
        await pytgcalls.unmute_stream(chat_id)
        k = await message.reply_text(lang["unmuted"])
    except (NoActiveGroupCall, NotInCallError):
        k = await message.reply_text(lang["notActive"])
    await delete_messages([message, k])


@client.on_message(
    filters.command(["ps", "pause"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def pause_stream(_, message: Message, lang):
    chat_id = message.chat.id
    try:
        await pytgcalls.pause_stream(chat_id)
        k = await message.reply_text(lang["paused"])
    except (NoActiveGroupCall, NotInCallError):
        k = await message.reply_text(lang["notActive"])
    await delete_messages([message, k])


@client.on_message(
    filters.command(["rs", "resume"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def resume_stream(_, message: Message, lang):
    chat_id = message.chat.id
    try:
        await pytgcalls.resume_stream(chat_id)
        k = await message.reply_text(lang["resumed"])
    except (NoActiveGroupCall, NotInCallError):
        k = await message.reply_text(lang["notActive"])
    await delete_messages([message, k])


@client.on_message(
    filters.command(["l", "loop"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def loop_track(_, message: Message, lang):
    chat_id = message.chat.id
    group = get_group(chat_id)
    if group["loop"]:
        set_group(chat_id, loop=False)
        k = await message.reply_text(lang["loopDisabled"])
    else:
        set_group(chat_id, loop=True)
        k = await message.reply_text(lang["loopEnabled"])
    await delete_messages([message, k])


@client.on_message(filters.command(["q", "queue"], config.PREFIXES) & ~filters.private)
@register
@language
@handle_error
async def show_queue(_, message: Message, lang):
    chat_id = message.chat.id
    queue = get_queue(chat_id)
    if len(queue) > 0:
        queue_str = "🎵 **Queue:**\n"
        for i, song in enumerate(queue._queue[:10], 1):
            queue_str += f"{i}. {song.title}\n"
        k = await message.reply_text(queue_str)
    else:
        k = await message.reply_text(lang["queueEmpty"])
    await delete_messages([message, k])


@client.on_message(
    filters.command(["stop", "leave"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def stop_stream(_, message: Message, lang):
    chat_id = message.chat.id
    try:
        set_group(chat_id, is_playing=False, now_playing=None)
        clear_queue(chat_id)
        await pytgcalls.leave_call(chat_id)
        k = await message.reply_text(lang["stopped"])
    except (NoActiveGroupCall, NotInCallError):
        k = await message.reply_text(lang["notActive"])
    await delete_messages([message, k])


@client.on_message(
    filters.command(["sh", "shuffle"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def shuffle_handler(_, message: Message, lang):
    chat_id = message.chat.id
    shuffle_queue(chat_id)
    k = await message.reply_text(lang["shuffled"])
    await delete_messages([message, k])


@client.on_message(
    filters.command(["ao", "adminsonly"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def admins_only(_, message: Message, lang):
    chat_id = message.chat.id
    group = get_group(chat_id)
    if group["admins_only"]:
        set_group(chat_id, admins_only=False)
        k = await message.reply_text(lang["adminsOnly"] % "Disabled")
    else:
        set_group(chat_id, admins_only=True)
        k = await message.reply_text(lang["adminsOnly"] % "Enabled")
    await delete_messages([message, k])


@client.on_message(
    filters.command(["lang", "language"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def set_lang(_, message: Message, lang):
    chat_id = message.chat.id
    lng = extract_args(message.text)
    if lng != "":
        langs = [
            file.replace(".json", "")
            for file in os.listdir(f"{os.getcwd()}/lang/")
            if file.endswith(".json")
        ]
        if lng == "list":
            k = await message.reply_text("\n".join(langs))
        elif lng in langs:
            set_group(chat_id, lang=lng)
            k = await message.reply_text(lang["langSet"] % lng)
        else:
            k = await message.reply_text(lang["notFound"])
        await delete_messages([message, k])


@client.on_message(
    filters.command(["ep", "export"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def export_queue(_, message: Message, lang):
    chat_id = message.chat.id
    queue = get_queue(chat_id)
    if len(queue) > 0:
        data = json.dumps([song.to_dict() for song in queue], indent=2)
        filename = f"{message.chat.username or message.chat.id}.json"
        with open(filename, "w") as file:
            file.write(data)
        await message.reply_document(
            filename, caption=lang["queueExported"] % len(queue)
        )
        os.remove(filename)
        await delete_messages([message])
    else:
        k = await message.reply_text(lang["queueEmpty"])
        await delete_messages([message, k])


@client.on_message(
    filters.command(["ip", "import"], config.PREFIXES) & ~filters.private
)
@register
@language
@only_admins
@handle_error
async def import_queue(_, message: Message, lang):
    if not message.reply_to_message or not message.reply_to_message.document:
        k = await message.reply_text(lang["replyToAFile"])
        return await delete_messages([message, k])
    chat_id = message.chat.id
    filename = await message.reply_to_message.download()
    data_str = None
    with open(filename, "r") as file:
        data_str = file.read()
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        k = await message.reply_text(lang["invalidFile"])
        return await delete_messages([message, k])
    try:
        temp_queue = []
        for song_dict in data:
            song = Song(song_dict["source"], message)
            song.title = song_dict["title"]
            temp_queue.append(song)
    except BaseException:
        k = await message.reply_text(lang["invalidFile"])
        return await delete_messages([message, k])
    group = get_group(chat_id)
    queue = get_queue(chat_id)
    if group["is_playing"]:
        for _song in temp_queue:
            await queue.put(_song)
    else:
        song = temp_queue[0]
        set_group(chat_id, is_playing=True, now_playing=song)
        ok, status = await song.parse()
        if not ok:
            raise Exception(status)
        await start_stream(song, lang)
        for _song in temp_queue[1:]:
            await queue.put(_song)
    k = await message.reply_text(lang["queueImported"] % len(temp_queue))
    await delete_messages([message, k])


@client.on_message(
    filters.command(["pl", "playlist"], config.PREFIXES) & ~filters.private
)
@register
@language
@handle_error
async def import_playlist(_, message: Message, lang):
    chat_id = message.chat.id
    group = get_group(chat_id)
    if group["admins_only"]:
        check = await is_admin(message)
        if not check:
            k = await message.reply_text(lang["notAllowed"])
            return await delete_messages([message, k])
    if message.reply_to_message:
        text = message.reply_to_message.text
    else:
        text = extract_args(message.text)
    if text == "":
        k = await message.reply_text(lang["notFound"])
        return await delete_messages([message, k])
    if "youtube.com/playlist?list=" in text:
        try:
            temp_queue = get_youtube_playlist(text, message)
        except BaseException:
            k = await message.reply_text(lang["notFound"])
            return await delete_messages([message, k])
    elif "open.spotify.com/playlist/" in text:
        if not config.SPOTIFY:
            k = await message.reply_text(lang["spotifyNotEnabled"])
            return await delete_messages([message, k])
        try:
            temp_queue = get_spotify_playlist(text, message)
        except BaseException:
            k = await message.reply_text(lang["notFound"])
            return await delete_messages([message, k])
    else:
        k = await message.reply_text(lang["invalidFile"])
        return await delete_messages([message, k])
    queue = get_queue(chat_id)
    if not group["is_playing"]:
        song = await temp_queue.__anext__()
        set_group(chat_id, is_playing=True, now_playing=song)
        ok, status = await song.parse()
        if not ok:
            raise Exception(status)
        await start_stream(song, lang)
        async for _song in temp_queue:
            await queue.put(_song)
        queue.get_nowait()
    else:
        async for _song in temp_queue:
            await queue.put(_song)
    k = await message.reply_text(lang["queueImported"] % len(group["queue"]))
    await delete_messages([message, k])


@client.on_message(
    filters.command(["update", "restart"], config.PREFIXES) & ~filters.private
)
@language
@handle_error
async def update_restart(_, message: Message, lang):
    check = await is_sudo(message)
    if not check:
        k = await message.reply_text(lang["notAllowed"])
        return await delete_messages([message, k])
    chats = all_groups()
    stats = await message.reply_text(lang["update"])
    for chat in chats:
        try:
            await pytgcalls.leave_call(chat)
        except (NoActiveGroupCall, NotInCallError):
            pass
    await stats.edit_text(lang["restart"])
    shutil.rmtree("downloads", ignore_errors=True)
    os.system(f"kill -9 {os.getpid()} && bash startup.sh")


@pytgcalls.on_update()
@language
@handle_error
async def stream_end(_, update: Update, lang):
    if isinstance(update, StreamEnded):
        chat_id = update.chat_id
        group = get_group(chat_id)
        if group["loop"]:
            await start_stream(group["now_playing"], lang)
        else:
            queue = get_queue(chat_id)
            if len(queue) > 0:
                next_song = await queue.get()
                if not next_song.parsed:
                    ok, status = await next_song.parse()
                    if not ok:
                        raise Exception(status)
                set_group(chat_id, now_playing=next_song)
                await start_stream(next_song, lang)
            else:
                if safone.get(chat_id) is not None:
                    try:
                        await safone[chat_id].delete()
                    except BaseException:
                        pass
                await set_title(chat_id, "", client=app)
                set_group(chat_id, is_playing=False, now_playing=None)
                try:
                    await pytgcalls.leave_call(chat_id)
                except (NoActiveGroupCall, NotInCallError):
                    pass


@pytgcalls.on_update(fl.chat_update(ChatUpdate.Status.LEFT_CALL))
@handle_error
async def closed_vc(_, update: Update):
    chat_id = update.chat_id
    if chat_id not in all_groups():
        if safone.get(chat_id) is not None:
            try:
                await safone[chat_id].delete()
            except BaseException:
                pass
        await set_title(chat_id, "", client=app)
        set_group(chat_id, now_playing=None, is_playing=False)
        clear_queue(chat_id)


client.start()
pytgcalls.run()
