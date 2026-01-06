from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlaylistConfig(Base):
    __tablename__ = "playlist_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Spotify auth state (stored per-silo DB)
    spotify_refresh_token: Mapped[str | None] = mapped_column(String, nullable=True)
    spotify_access_token: Mapped[str | None] = mapped_column(String, nullable=True)
    spotify_access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Spotify playlist created/linked for this silo
    spotify_playlist_id: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SongEntry(Base):
    __tablename__ = "song_entries"

    __table_args__ = (
        UniqueConstraint("user", "spotify_track_id", name="uq_songentry_user_spotify_track"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    spotify_track_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    spotify_track_uri: Mapped[str | None] = mapped_column(String, nullable=True)

    song: Mapped[str] = mapped_column(String, nullable=False)
    artist: Mapped[str] = mapped_column(String, nullable=False)
    album_art_url: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
