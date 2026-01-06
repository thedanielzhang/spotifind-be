from __future__ import annotations

from sqlalchemy.orm import Session

from . import crud, models, schemas
from .spotify_client import get_valid_access_token, add_track_to_playlist, SpotifyApiError, SpotifyAuthError


def add_song_to_app_playlist(db: Session, song_in: schemas.SongCreate) -> models.SongEntry:
    existing = crud.find_song_by_user_and_track(db, song_in.user, song_in.spotify_track_id)
    if existing is not None:
        return existing

    entry = models.SongEntry(
        spotify_track_id=song_in.spotify_track_id,
        spotify_track_uri=song_in.spotify_track_uri,
        song=song_in.song,
        artist=song_in.artist,
        album_art_url=song_in.album_art_url,
        user=song_in.user,
        user_avatar_url=song_in.user_avatar_url,
        comment=song_in.comment,
    )
    entry = crud.create_song(db, entry)

    # Best-effort add to Spotify playlist if configured
    cfg = crud.get_playlist_config(db)
    if cfg and cfg.spotify_refresh_token and cfg.spotify_playlist_id and song_in.spotify_track_uri:
        try:
            access_token = get_valid_access_token(db, cfg)
            add_track_to_playlist(access_token, cfg.spotify_playlist_id, song_in.spotify_track_uri)
        except (SpotifyAuthError, SpotifyApiError):
            # For POC: don't fail the DB write if Spotify is down.
            # In production: you'd outbox + retry.
            pass

    return entry
