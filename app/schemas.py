from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class PlaylistConfigStatus(BaseModel):
    exists: bool
    name: str | None
    spotify_playlist_id: str | None

    description: str | None = None
    cover_image_url: str | None = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class PlaylistConfigCreate(BaseModel):
    name: str | None = None
    description: str | None = None
    cover_image_url: str | None = None


class SpotifyConnectStatus(BaseModel):
    ok: bool = True


class SongCreate(BaseModel):
    spotify_track_id: str
    spotify_track_uri: str | None = None

    song: str
    artist: str
    album_art_url: str | None = None

    user: str
    user_avatar_url: str | None = None
    comment: str | None = None


class SongOut(BaseModel):
    id: int
    spotify_track_id: str
    spotify_track_uri: str | None

    song: str
    artist: str
    album_art_url: str | None

    user: str
    user_avatar_url: str | None
    comment: str | None

    created_at: datetime

    class Config:
        from_attributes = True
