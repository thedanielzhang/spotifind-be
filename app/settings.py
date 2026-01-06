from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"

APP_ENV_PATH = CONFIG_DIR / "app_env.json"
SILO_ENV_PATH = Path(
    os.getenv("SILO_ENV_FILE", str(CONFIG_DIR / "silo_env.local.json"))
)

_TEMPLATE_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


# ---------------------------------------------------------
# Load raw config
# ---------------------------------------------------------

def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


_silo_env: Dict[str, Any] = _load_json(SILO_ENV_PATH)
_app_env_raw: Dict[str, Any] = _load_json(APP_ENV_PATH)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _stringify(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _lookup_raw(key: str) -> Optional[str]:
    """
    Raw lookup without template resolution.
    Precedence:
      1. OS environment
      2. silo_env
      3. app_env (raw)
    """
    if key in os.environ:
        return os.environ[key]
    if key in _silo_env:
        return _stringify(_silo_env[key])
    if key in _app_env_raw:
        return _stringify(_app_env_raw[key])
    return None


def _resolve_templates(value: str, max_passes: int = 3) -> str:
    """
    Resolve {{KEY}} placeholders using OS env + silo_env + app_env_raw.
    """
    current = value
    for _ in range(max_passes):
        def repl(match: re.Match) -> str:
            k = match.group(1)
            v = _lookup_raw(k)
            if v is None:
                raise RuntimeError(
                    f"Unresolved template variable '{{{{{k}}}}}' in config value '{value}'"
                )
            return v

        next_val = _TEMPLATE_RE.sub(repl, current)
        if next_val == current:
            break
        current = next_val
    return current


def get_setting(key: str) -> str:
    """
    Strict config lookup.

    Resolution order:
      1. OS env
      2. silo_env
      3. app_env (template-resolved)

    Raises RuntimeError if missing.
    """
    if key in os.environ:
        return os.environ[key]

    if key in _silo_env:
        return _stringify(_silo_env[key])  # type: ignore

    if key in _app_env_raw:
        raw = _stringify(_app_env_raw[key])
        if raw is None:
            raise RuntimeError(f"Config key '{key}' is null")
        return _resolve_templates(raw)

    raise RuntimeError(f"Missing required config key: {key}")


# ---------------------------------------------------------
# Silo identity / URLs (REQUIRED)
# ---------------------------------------------------------

SILO_ID = get_setting("SILO_ID")
SILO_NAME = get_setting("SILO_NAME")
SILO_BASE_URL = get_setting("SILO_BASE_URL")

# ---------------------------------------------------------
# App ports (REQUIRED)
# ---------------------------------------------------------

APP_FE_PORT = int(get_setting("APP_FE_PORT"))
APP_BE_PORT = int(get_setting("APP_BE_PORT"))
APP_DB_PORT = int(get_setting("APP_DB_PORT"))

# ---------------------------------------------------------
# Core runtime (REQUIRED)
# ---------------------------------------------------------

DATABASE_URL = get_setting("DATABASE_URL")

# ---------------------------------------------------------
# Admin auth (REQUIRED)
# ---------------------------------------------------------

ADMIN_USERNAME = get_setting("ADMIN_USERNAME")
ADMIN_PASSWORD = get_setting("ADMIN_PASSWORD")
ADMIN_JWT_SECRET = get_setting("ADMIN_JWT_SECRET")

# ---------------------------------------------------------
# Spotify app credentials (REQUIRED)
# ---------------------------------------------------------

SPOTIFY_CLIENT_ID = get_setting("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = get_setting("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = get_setting("SPOTIFY_REDIRECT_URI")
SPOTIFY_SCOPES = get_setting("SPOTIFY_SCOPES")

FRONTEND_ADMIN_URL = get_setting("FRONTEND_ADMIN_URL")

# ---------------------------------------------------------
# Playlist metadata templates (REQUIRED)
# ---------------------------------------------------------

PLAYLIST_TITLE_TEMPLATE = get_setting("PLAYLIST_TITLE_TEMPLATE")
PLAYLIST_DESCRIPTION_TEMPLATE = get_setting("PLAYLIST_DESCRIPTION_TEMPLATE")
PLAYLIST_COVER_IMAGE_URL = get_setting("PLAYLIST_COVER_IMAGE_URL")


def derived_playlist_title() -> str:
    return _resolve_templates(PLAYLIST_TITLE_TEMPLATE)


def derived_playlist_description() -> str:
    return _resolve_templates(PLAYLIST_DESCRIPTION_TEMPLATE)
