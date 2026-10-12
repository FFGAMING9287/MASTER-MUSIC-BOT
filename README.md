<h1 align= center><b>⭐️ Music Player ⭐️</b></h1>
<h3 align = center> A Telegram Music Bot written in Python using Pyrogram and Py-Tgcalls </h3>

<p align="center">
<a href="https://python.org"><img src="http://forthebadge.com/images/badges/made-with-python.svg" alt="made-with-python"></a>
<br>
    <img src="https://img.shields.io/github/license/AsmSafone/MusicPlayer?style=for-the-badge" alt="LICENSE">
    <img src="https://img.shields.io/github/contributors/AsmSafone/MusicPlayer?style=for-the-badge" alt="Contributors">
    <img src="https://img.shields.io/github/repo-size/AsmSafone/MusicPlayer?style=for-the-badge" alt="Repository Size"> <br>
    <img src="https://img.shields.io/github/forks/AsmSafone/MusicPlayer?style=for-the-badge" alt="Forks">
    <img src="https://img.shields.io/github/stars/AsmSafone/MusicPlayer?style=for-the-badge" alt="Stars">
    <img src="https://img.shields.io/github/watchers/AsmSafone/MusicPlayer?style=for-the-badge" alt="Watchers">
    <img src="https://img.shields.io/github/commit-activity/w/AsmSafone/MusicPlayer?style=for-the-badge" alt="Commit Activity">
    <img src="https://img.shields.io/github/issues/AsmSafone/MusicPlayer?style=for-the-badge" alt="Issues">
</p>

## ✨ <a name="features"></a>Features

### ⚡️ Fast & Light

Starts streaming your inputs while downloading and converting them. Also, it
doesn't make produce files.

### 👮🏻‍♀️ Safe and handy

Restricts control and sensitive commands to admins.

### 🗑 Clean and spam free

Deletes old playing trash to keep your chats clean.

### 😎 Has cool controls

Lets you switch stream mode, loop, pause, resume, mute, unmute anytime.

### 🖼 Has cool thumbnails

Response your commands with cool thumbnails on the chat.

### 😉 Streams whatever you like

You can stream audio or video files, YouTube videos with any duration,
YouTube lives, YouTube playlists and even custom live streams like radios or m3u8 links or files in
the place it is hosted!

### 📊 Streams in multiple places

Allows you to stream different things in multiple chats simultaneously. Each
chat will have its own song queue.

### 🗣 Speaks different languages

Music Player is multilingual and speaks [various languages](#languages),
thanks to the translators.

## 🚀 <a name="deploy"></a>Deploy

[![Deploy on Heroku](https://www.herokucdn.com/deploy/button.svg)](https://deploy.safone.dev)

Note: `First Fork The Repo Then Click On Deploy To Heroku Button!`


## ☁️ <a name="self_host"></a>Self Host

- Legecy Method
```bash
$ git clone https://github.com/AsmSafone/MusicPlayer
$ cd MusicPlayer
$ sudo apt install git curl python3-pip ffmpeg -y
$ pip3 install -U pip
$ pip3 install -U -r requirements.txt
$ cp sample.env .env
# < edit .env with your own values >
$ python3 main.py
```
Or you can use this One-Liner to save your time :

```
git clone https://github.com/AsmSafone/MusicPlayer && cd MusicPlayer && sudo apt install git curl python3-pip ffmpeg -y && pip3 install -U pip && pip3 install -U -r requirements.txt
```
Make sure to edit the .env file accordingly,
```
cp sample.env .env
```
Run it using,
```
python3 main.py
```

- Docker Build Method
```bash
$ git clone https://github.com/AsmSafone/MusicPlayer
$ cd MusicPlayer
$ cp sample.env .env
# < edit .env with your own values >
$ sudo docker build . -t musicplayer
$ sudo docker run musicplayer
```

## ⚒ <a name="configs"></a>Configs

- `API_ID`: Telegram app id from https://my.telegram.org/apps.
- `API_HASH`: Telegram app hash from https://my.telegram.org/apps.
- `SESSION`: Pyrogram string session. You can generate from [here](https://replit.com/@AsmSafone/genStr).
- `SUDOERS`: ID of sudo users (separate multiple ids with space).
- `BOT_TOKEN`: Telegram bot token from https://t.me/botfather. (optional)
- `QUALITY`: Custom stream quality (high/medium/low) for the userbot in vc. Default: `high`
- `PREFIX`: Bot commad prefixes (separate multiple prefix with space). Eg: `! /`
- `LANGUAGE`: An [available](#languages) bot language (can change it anytime). Default: `en`
- `STREAM_MODE`: An stream mode like audio or video (can change it anytime). Default: `audio`
- `MOVIE_ALLOWED_DOWNLOAD_HOSTS`: Comma-separated exact HTTPS hostnames authorized by the operator. Empty by default; movie downloads stay disabled until configured.
- `MOVIE_DOWNLOAD_DIR`: Temporary/cache directory for movie media. Default: `/tmp/master-music-bot/movies`.
- `MOVIE_MAX_DOWNLOAD_MB`, `MOVIE_CACHE_TTL_HOURS`, `MOVIE_MAX_CONCURRENT_DOWNLOADS`: Download size cap, cache retention, and download concurrency settings. See [movie integration details](./MOVIE_INTEGRATION_README.md).
- `ADMINS_ONLY`: Put `True` if you want to make /play commands only for admins. Default: `False`
- `SPOTIFY_CLIENT_ID`: Spotify client id get it from [here](https://developer.spotify.com/dashboard/applications). (optional)
- `SPOTIFY_CLIENT_SECRET`: Spotify client secret get it from [here](https://developer.spotify.com/dashboard/applications). (optional)


## 📄 <a name="commands"></a>Commands

Command | Description
:--- | :---
• !ping | Check if alive or not
• !start / !help | Show the help for commands
• !mode / !switch | Switch the stream mode (audio/video)
• !p / !play [song name or youtube link] | Play a song in vc, if already playing add to queue
• !radio / !stream [radio url or stream link] | Play a live stream in vc, if already playing add to queue
• !pl / !playlist [playlist link] | Play the whole youtube playlist at once
• !skip / !next | Skip to the next song
• !m / !mute | Mute the current stream
• !um / !unmute | Unmute the muted stream
• !ps / !pause | Pause the current stream
• !rs / !resume | Resume the paused stream
• !list / !queue | Show the songs in the queue
• !mix / !shuffle | Shuflle the queued playlist
• !loop / !repeat | Enable or disable the loop mode
• !lang / language [language code] | Set the bot language in group
• !ip / !import | Import queue from exported file
• !ep / !export | Export the queue for import in future
• !stop / !leave | Leave from vc and clear the queue
• !update / !restart | Update and restart your music player
• /movie [title] or !movie [title] | Search titles, select episode/language/quality, download, and queue or stream authorized media in a voice chat. See [movie integration details](./MOVIE_INTEGRATION_README.md).

## 🗣 <a name="languages"></a>Languages

```text
ar    Arabic
bn    Bengali
cn    Chinese
de    German
en    English
fr    French
hi    Hindi
ja    Japanese
nl    Dutch
ru    Russian
te    Telegu
tr    Turkish
```

## 💜 <a name="contribute"></a>Contribute

New languages, bug fixes and improvements following
[our contribution guidelines](./CONTRIBUTING.md) are warmly welcomed!

## 🛫 <a name="supports"></a>Supports

For any kind of help join [our support group](https://t.me/AsmSupport) or raise an [issue](https://github.com/AsmSafone/MusicPlayer/issues).

## ✨ <a name="credits"></a>Credits

- [Me](https://github.com/AsmSafone) for [Noting](https://github.com/AsmSafone/MusicPlayer) 😬
- [Dan](https://github.com/delivrance) for [Pyrogram](https://github.com/pyrogram/pyrogram) ❤️
- [Laky-64](https://github.com/Laky-64) for [Py-TgCalls](https://github.com/pytgcalls/pytgcalls) ❤️
- And Thanks To All [Contributors](https://github.com/AsmSafone/MusicPlayer/graphs/contributors)! ❤️

## 📃 <a name="license"></a>License

Music Player is licenced under the GNU Affero General Public License v3.0.
Read more [here](./LICENSE).
