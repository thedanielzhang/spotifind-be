from __future__ import annotations

import os
import re
from typing import Optional

from dotenv import load_dotenv

# Load .env for local dev (Railway env vars still win because we don't override)
load_dotenv(override=False)

_TEMPLATE_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")

def _require(key: str) -> str:
    val = os.getenv(key)
    if val is None or val == "":
        raise RuntimeError(f"Missing required env var: {key}")
    return val

def _optional(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(key, default)

def _render_templates(value: str, max_passes: int = 3) -> str:
    """
    Resolve {{KEY}} using *environment variables only*.
    """
    current = value
    for _ in range(max_passes):
        def repl(match: re.Match) -> str:
            k = match.group(1)
            v = os.getenv(k)
            if v is None:
                raise RuntimeError(
                    f"Unresolved template variable '{{{{{k}}}}}' in '{value}'"
                )
            return v

        next_val = _TEMPLATE_RE.sub(repl, current)
        if next_val == current:
            break
        current = next_val
    return current

# ---------------------------------------------------------
# Core runtime (REQUIRED)
# ---------------------------------------------------------
DATABASE_URL = _require("DATABASE_URL")

# ---------------------------------------------------------
# Admin auth (REQUIRED)
# ---------------------------------------------------------
ADMIN_USERNAME = _require("ADMIN_USERNAME")
ADMIN_PASSWORD = _require("ADMIN_PASSWORD")
ADMIN_JWT_SECRET = _require("ADMIN_JWT_SECRET")

# ---------------------------------------------------------
# Spotify app credentials (REQUIRED)
# ---------------------------------------------------------
SPOTIFY_CLIENT_ID = _require("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = _require("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = _require("SPOTIFY_REDIRECT_URI")
SPOTIFY_SCOPES = _require("SPOTIFY_SCOPES")

# ---------------------------------------------------------
# Frontend / CORS (REQUIRED-ish)
# ---------------------------------------------------------
FRONTEND_ADMIN_URL = _require("FRONTEND_ADMIN_URL")
FRONTEND_ORIGIN = _optional("FRONTEND_ORIGIN")  # optional, but recommended

# ---------------------------------------------------------
# Optional identity (used for templates)
# ---------------------------------------------------------
SILO_ID = _optional("SILO_ID", "local")
SILO_NAME = _optional("SILO_NAME", "Local")
SILO_BASE_URL = _optional("SILO_BASE_URL", "http://127.0.0.1")

# ---------------------------------------------------------
# Playlist metadata templates (REQUIRED)
# ---------------------------------------------------------
PLAYLIST_TITLE_TEMPLATE = f'{SILO_NAME} Playlist'
PLAYLIST_DESCRIPTION_TEMPLATE = f'A shared playlist for {SILO_NAME}'
PLAYLIST_COVER_IMAGE_URL = _require("PLAYLIST_COVER_IMAGE_URL")

def derived_playlist_title() -> str:
    return _render_templates(PLAYLIST_TITLE_TEMPLATE)

def derived_playlist_description() -> str:
    return _render_templates(PLAYLIST_DESCRIPTION_TEMPLATE)
