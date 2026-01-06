from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from . import models
from .settings import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, SPOTIFY_SCOPES

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


class SpotifyAuthError(Exception):
    pass


class SpotifyApiError(Exception):
    pass


def _get_spotify_client_settings():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise RuntimeError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
    return SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI


def build_spotify_authorize_url(state: str) -> str:
    client_id, _, redirect_uri = _get_spotify_client_settings()
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SPOTIFY_SCOPES,
        "state": state,
        "show_dialog": "true",
    }
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    client_id, client_secret, redirect_uri = _get_spotify_client_settings()

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    resp = httpx.post(SPOTIFY_TOKEN_URL, data=data, timeout=10)
    if resp.status_code != 200:
        raise SpotifyAuthError(f"Token exchange failed: {resp.status_code} {resp.text}")

    return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    client_id, client_secret, _ = _get_spotify_client_settings()

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    resp = httpx.post(SPOTIFY_TOKEN_URL, data=data, timeout=10)
    if resp.status_code != 200:
        raise SpotifyAuthError(f"Refresh failed: {resp.status_code} {resp.text}")

    return resp.json()


def get_valid_access_token(db: Session, cfg: models.PlaylistConfig) -> str:
    if not cfg.spotify_refresh_token:
        raise SpotifyAuthError("No refresh token stored")

    now = datetime.now(timezone.utc)
    if cfg.spotify_access_token and cfg.spotify_access_token_expires_at:
        # refresh ~60s early
        if cfg.spotify_access_token_expires_at - now > timedelta(seconds=60):
            return cfg.spotify_access_token

    token_data = refresh_access_token(cfg.spotify_refresh_token)
    access_token = token_data.get("access_token")
    expires_in = int(token_data.get("expires_in", 3600))

    if not access_token:
        raise SpotifyAuthError("Refresh response missing access_token")

    cfg.spotify_access_token = access_token
    cfg.spotify_access_token_expires_at = now + timedelta(seconds=expires_in)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)

    return access_token


def get_user_profile(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = httpx.get(f"{SPOTIFY_API_BASE}/me", headers=headers, timeout=10)
    if resp.status_code != 200:
        raise SpotifyApiError(f"Get profile failed: {resp.status_code} {resp.text}")
    return resp.json()


def create_playlist_for_user(access_token: str, user_id: str, name: str, description: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"name": name, "description": description, "public": False}
    resp = httpx.post(f"{SPOTIFY_API_BASE}/users/{user_id}/playlists", headers=headers, json=payload, timeout=10)
    if resp.status_code not in (200, 201):
        raise SpotifyApiError(f"Create playlist failed: {resp.status_code} {resp.text}")
    return resp.json()


def add_track_to_playlist(access_token: str, playlist_id: str, track_uri: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"uris": [track_uri]}
    resp = httpx.post(f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks", headers=headers, json=payload, timeout=10)
    if resp.status_code not in (200, 201):
        raise SpotifyApiError(f"Add track failed: {resp.status_code} {resp.text}")


def search_tracks(access_token: str, query: str, limit: int = 10) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"q": query, "type": "track", "limit": limit}
    resp = httpx.get(f"{SPOTIFY_API_BASE}/search", headers=headers, params=params, timeout=10)
    if resp.status_code != 200:
        raise SpotifyApiError(f"Spotify search failed: {resp.status_code} {resp.text}")
    return resp.json()
