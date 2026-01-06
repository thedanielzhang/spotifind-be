from __future__ import annotations

from sqlalchemy.orm import Session

from . import models


def get_playlist_config(db: Session) -> models.PlaylistConfig | None:
    return db.query(models.PlaylistConfig).first()


def ensure_playlist_config_row(db: Session) -> models.PlaylistConfig:
    cfg = get_playlist_config(db)
    if cfg is not None:
        return cfg
    cfg = models.PlaylistConfig()
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def list_songs(db: Session) -> list[models.SongEntry]:
    return (
        db.query(models.SongEntry)
        .order_by(models.SongEntry.created_at.desc())
        .all()
    )


def find_song_by_user_and_track(db: Session, user: str, spotify_track_id: str) -> models.SongEntry | None:
    return (
        db.query(models.SongEntry)
        .filter(models.SongEntry.user == user, models.SongEntry.spotify_track_id == spotify_track_id)
        .first()
    )


def create_song(db: Session, song: models.SongEntry) -> models.SongEntry:
    db.add(song)
    db.commit()
    db.refresh(song)
    return song
