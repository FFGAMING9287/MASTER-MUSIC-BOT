# Movie search integration

`MASTER-MUSIC-BOT` includes a Telegram command that searches the Movie Downloader API and displays matching titles and available episode links.

## Command

```text
/movie <title>
/movie Overflow
!movie Overflow
```

`/movie` is accepted regardless of the configured bot prefix. The configured prefix also works (`!movie` by default). The existing mute alias remains `!m` when the configured prefix is `!`; movie search does not take over the `m` alias.

## API

The bot makes an asynchronous request to:

```text
https://movie-downloader-api.vercel.app/api/search?q=<URL-encoded title>
```

No API key is configured or required by this integration. The client handles the API's `results` response, including title, year, type, rating, country, language, season, episode, and quality-link fields. The bot shows up to five matching titles and adds a capped set of buttons for available episode links, choosing the highest listed quality per language for the first available episode.

## Configuration and testing

No additional environment variables are required. Install the normal project dependencies and start the bot as usual:

```bash
pip install -r requirements.txt
python main.py
```

API timeouts, non-success HTTP responses, and malformed responses are handled without exposing exception details in the chat. If the public API is unavailable, the bot tells the user to try again later.
