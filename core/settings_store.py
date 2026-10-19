"""Private runtime settings for owner-managed API endpoints and cookies.

Secrets are Fernet-encrypted in the settings JSON. The encryption key and data
live in a private runtime directory and must not be committed to Git.
"""

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken

DEFAULT_API_URLS = {
    "movie_box": "https://movie-box-api.co08.art/api",
    "legacy_movie": "https://movie-downloader-api.vercel.app/api",
    "adult": "https://fulux-downloader-api.vercel.app/api",
}

_DEFAULT_COOKIE_LIMIT = 100_000
_LOCK = threading.RLock()


def _settings_dir() -> Path:
    value = os.getenv("BOT_SETTINGS_DIR", "bot_settings_data")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _paths():
    directory = _settings_dir()
    return directory, directory / "settings.json", directory / ".fernet.key"


def _ensure_directory(directory: Path) -> None:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass


def _fernet(create: bool = False) -> Fernet:
    directory, _, key_path = _paths()
    _ensure_directory(directory)
    if not key_path.exists():
        if not create:
            raise RuntimeError("Settings encryption key is not available.")
        key = Fernet.generate_key()
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as key_file:
                key_file.write(key)
        except FileExistsError:
            key = key_path.read_bytes()
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
    else:
        key = key_path.read_bytes()
    try:
        return Fernet(key.strip())
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Settings encryption key is invalid.") from exc


def _load() -> dict:
    directory, settings_path, _ = _paths()
    if not settings_path.exists():
        return {"apis": {}, "custom_apis": {}, "cookies": {}}
    try:
        with settings_path.open("r", encoding="utf-8") as settings_file:
            data = json.load(settings_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Settings file is unreadable.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Settings file has an invalid structure.")
    data.setdefault("apis", {})
    data.setdefault("custom_apis", {})
    data.setdefault("cookies", {})
    return data


def _save(data: dict) -> None:
    directory, settings_path, _ = _paths()
    _ensure_directory(directory)
    fd, temp_name = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            os.fchmod(temp_file.fileno(), 0o600)
            json.dump(data, temp_file, ensure_ascii=False, separators=(",", ":"))
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, settings_path)
        try:
            os.chmod(settings_path, 0o600)
        except OSError:
            pass
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def validate_https_url(value: str) -> str:
    value = (value or "").strip()
    parts = urlsplit(value)
    if (
        parts.scheme.lower() != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError(
            "Enter an HTTPS base URL without credentials, query, or fragment."
        )
    if any(character.isspace() for character in value):
        raise ValueError("The URL cannot contain spaces.")
    return value.rstrip("/")


def _encrypt(value: str) -> str:
    return _fernet(create=True).encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(value: str):
    try:
        return _fernet(create=False).decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, OSError, RuntimeError, ValueError):
        return None


def get_api_url(key: str, default: str | None = None) -> str:
    fallback = default or DEFAULT_API_URLS.get(key, "")
    with _LOCK:
        item = _load().get("apis", {}).get(key)
        encrypted = item.get("url") if isinstance(item, dict) else None
        value = _decrypt(encrypted) if encrypted else None
        return value or fallback


def set_api_url(key: str, value: str) -> None:
    url = validate_https_url(value)
    with _LOCK:
        data = _load()
        data["apis"][key] = {"url": _encrypt(url)}
        _save(data)


def get_api_urls(key: str, defaults: list[str]) -> list[str]:
    with _LOCK:
        item = _load().get("apis", {}).get(key)
        encrypted_urls = item.get("urls") if isinstance(item, dict) else None
        if not isinstance(encrypted_urls, list):
            return list(defaults)
        urls = [_decrypt(value) for value in encrypted_urls if isinstance(value, str)]
        return [value for value in urls if value] or list(defaults)


def set_api_urls(key: str, values: list[str]) -> None:
    urls = [validate_https_url(value) for value in values if value.strip()]
    if not urls:
        raise ValueError("Enter at least one HTTPS URL.")
    with _LOCK:
        data = _load()
        data["apis"][key] = {"urls": [_encrypt(value) for value in urls]}
        _save(data)


def get_cookie(service: str):
    with _LOCK:
        encrypted = _load().get("cookies", {}).get(service)
        return _decrypt(encrypted) if isinstance(encrypted, str) else None


def has_cookie(service: str) -> bool:
    return bool(get_cookie(service))


def set_cookie(service: str, value: str) -> None:
    value = value.strip()
    if not value or len(value.encode("utf-8")) > _DEFAULT_COOKIE_LIMIT:
        raise ValueError("Cookie content is empty or exceeds the size limit.")
    with _LOCK:
        data = _load()
        data["cookies"][service] = _encrypt(value)
        _save(data)


def delete_cookie(service: str) -> bool:
    with _LOCK:
        data = _load()
        existed = data.get("cookies", {}).pop(service, None) is not None
        if existed:
            _save(data)
        return existed


def get_custom_apis() -> dict:
    with _LOCK:
        stored = _load().get("custom_apis", {})
        output = {}
        for name, item in stored.items():
            if not isinstance(item, dict):
                continue
            url = _decrypt(item.get("url", ""))
            if url:
                output[name] = {
                    "purpose": str(item.get("purpose", "")),
                    "url": url,
                }
        return output


def set_custom_api(name: str, purpose: str, url: str) -> None:
    name = name.strip().lower()
    purpose = purpose.strip()
    url = validate_https_url(url)
    if not re.fullmatch(r"[a-z0-9_-]{2,32}", name):
        raise ValueError("Use a 2–32 character API name with letters, digits, _ or -.")
    if len(purpose) < 3 or len(purpose) > 160:
        raise ValueError("Describe the API's use in 3–160 characters.")
    with _LOCK:
        data = _load()
        data["custom_apis"][name] = {"purpose": purpose, "url": _encrypt(url)}
        _save(data)


def delete_custom_api(name: str) -> bool:
    with _LOCK:
        data = _load()
        existed = data.get("custom_apis", {}).pop(name, None) is not None
        if existed:
            _save(data)
        return existed


def create_cookie_tempfile(service: str):
    """Materialize a decrypted cookie file briefly for tools such as yt-dlp."""
    value = get_cookie(service)
    if not value:
        return None
    fd, name = tempfile.mkstemp(prefix="bot-cookie-", suffix=".txt")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as cookie_file:
            cookie_file.write(value)
        return name
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def delete_cookie_tempfile(path) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError:
        pass
