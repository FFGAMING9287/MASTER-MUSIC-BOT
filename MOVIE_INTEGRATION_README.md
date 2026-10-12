# Movie search and episode streaming

`MASTER-MUSIC-BOT` keeps the existing movie-result text UI and adds callback buttons for individual episode, language, and quality choices. Results are paginated and can be filtered by language or quality; selecting an option starts an asynchronous download while the Telegram bot continues handling other messages. The original result buttons remain available after selection.

## Commands and controls

```text
/movie <title>
/movie Overflow
!movie Overflow
```

`/movie` works regardless of the configured prefix. The configured-prefix form also works (`!movie` by default); the existing `!m` mute alias is unchanged.

- The selected item shows download progress (percentage when size is known, downloaded size, speed, and ETA when available), plus **Download Status**, **Cancel**, **Retry**, and **Back to Results** actions as appropriate.
- If a voice-chat stream is active after the download completes, the requester can **Queue**, **Cancel**, or ask a group admin to **Replace** it. Replacement requires a second confirmation and is admin-only.
- If the group has no active voice chat, the downloaded file is kept in cache and the bot asks the user to start one, then tap **Retry**.
- Movies stream as video using the selected source quality. Existing `/pause`, `/resume`, `/skip`, and `/stop` commands continue to provide the bot's supported playback controls; pause/resume/skip/stop remain admin-only. This PyTgCalls integration does not add a seek/scrub control.

## API and supported media

Search uses the public endpoint:

```text
https://movie-downloader-api.vercel.app/api/search?q=<URL-encoded title>
```

The bot accepts only direct HTTPS media responses in supported video formats (MP4, WebM, MKV, MOV, AVI, MPEG, or TS). If a link serves a web page instead of a media file, the bot reports that limitation; it does not scrape a provider page or assume the page is playable. Provider-specific resolution should only be added for an authorized provider with a documented integration.

## Authorization and configuration

The exact `movie-downloader-api.vercel.app` hostname used by the configured search API is allowed by default. The downloader revalidates every redirect host, requires public DNS addresses, and rejects unapproved hosts, non-HTTPS URLs, webpage responses, and files above the configured cap. Add only additional exact hostnames for sources you own or are authorized to use. A public search API or a `video/*` content type does not by itself establish permission to copy or stream a title.

Set these environment variables in `.env` or the deployment environment:

- `MOVIE_ALLOWED_DOWNLOAD_HOSTS`: optional comma-separated additional exact hostnames, with no scheme/path or wildcard. `movie-downloader-api.vercel.app` is built in; add any other authorized redirect host separately if one is returned by the provider.
- `MOVIE_DOWNLOAD_DIR`: temporary/cache directory. Default: `/tmp/master-music-bot/movies` (ephemeral storage may be cleared on redeploy).
- `MOVIE_MAX_DOWNLOAD_MB`: per-file size cap. Default: `2048`.
- `MOVIE_CACHE_TTL_HOURS`: cache retention. Default: `24` hours. Expired files are removed on later downloads, while active and queued files are protected.
- `MOVIE_MAX_CONCURRENT_DOWNLOADS`: concurrent downloads. Default: `2`.

The existing project dependencies already include `aiohttp` and `aiofiles`; no new provider or streaming dependency is required.
