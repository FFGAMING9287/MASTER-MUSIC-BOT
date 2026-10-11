# Movie search integration

`MASTER-MUSIC-BOT` includes a Telegram command that searches the Movie Downloader API and displays matching titles and available episode links.

## Command

```text
/movie <title>
/movie Overflow
```

The command works in groups. `/m` remains the existing mute alias, so it is intentionally not used for movie search.

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
