from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from . import crud, schemas
from .auth import create_admin_token, get_current_admin
from .settings import (
    FRONTEND_ADMIN_URL,
    FRONTEND_ORIGIN,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    derived_playlist_title,
    derived_playlist_description,
)
from .spotify_client import (
    build_spotify_authorize_url,
    exchange_code_for_tokens,
    get_user_profile,
    create_playlist_for_user,
    get_valid_access_token,
    search_tracks,
    SpotifyAuthError,
    SpotifyApiError,
)
from .services import add_song_to_app_playlist
print("FRONTEND_ORIGIN =", FRONTEND_ORIGIN)

app = FastAPI()

# Create tables (note: does not migrate existing tables)
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_ORIGIN
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


# ---------- Admin auth ----------

@app.post("/admin/login")
def admin_login(response: Response, creds: schemas.AdminLoginRequest):
    if creds.username != ADMIN_USERNAME or creds.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin credentials.")

    token = create_admin_token(sub=creds.username)

    # SameSite=Lax is fine for 127.0.0.1:<port> usage; keep it simple for POC
    response.set_cookie(
        key="admin_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return {"ok": True}


@app.post("/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie("admin_session", path="/")
    return {"ok": True}


# ---------- Admin session check ----------

@app.get("/admin/me")
def admin_me(_: str = Depends(get_current_admin)):
    """
    Simple endpoint to verify the admin_session cookie is valid.
    FE uses this to gate admin flows and show logged-in state.
    """
    return {"ok": True}


# ---------- Playlist config status (public) ----------
# This is what the FE uses to decide "isReady" and populate the playlist card.

@app.get("/playlist/config", response_model=schemas.PlaylistConfigStatus)
def get_playlist_config_status(db: Session = Depends(get_db)):
    cfg = crud.get_playlist_config(db)

    title = derived_playlist_title()
    desc = derived_playlist_description()
    cover = ""

    if cfg is None:
        return schemas.PlaylistConfigStatus(
            exists=False,
            name=title,
            spotify_playlist_id=None,
            description=desc,
            cover_image_url=cover,
        )

    return schemas.PlaylistConfigStatus(
        exists=True,
        name=title,
        spotify_playlist_id=cfg.spotify_playlist_id,
        description=desc,
        cover_image_url=cover,
    )


# ---------- Admin "ensure config row exists" ----------
# Kept for your admin flow; right now it just creates the row.

@app.post("/playlist/config")
def create_playlist_config(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    crud.ensure_playlist_config_row(db)
    return {"ok": True}


# ---------- Spotify OAuth ----------

@app.get("/admin/spotify/authorize")
def admin_spotify_authorize(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    cfg = crud.ensure_playlist_config_row(db)
    state = str(cfg.id)  # simple state: config id
    url = build_spotify_authorize_url(state=state)
    return {"authorize_url": url}


@app.get("/admin/spotify/callback")
def admin_spotify_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    if error:
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}?spotify_error={error}")

    if not code or not state:
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}?spotify_error=missing_code_or_state")

    cfg = crud.get_playlist_config(db)
    if cfg is None:
        cfg = crud.ensure_playlist_config_row(db)

    try:
        token_data = exchange_code_for_tokens(code)

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = int(token_data.get("expires_in", 3600))

        if not access_token or not refresh_token:
            return RedirectResponse(f"{FRONTEND_ADMIN_URL}?spotify_error=missing_tokens")

        # store tokens
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        cfg.spotify_access_token = access_token
        cfg.spotify_refresh_token = refresh_token
        cfg.spotify_access_token_expires_at = now + timedelta(seconds=expires_in)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

        # create playlist if not already created
        if not cfg.spotify_playlist_id:
            profile = get_user_profile(access_token)
            user_id = profile.get("id")
            if not user_id:
                return RedirectResponse(f"{FRONTEND_ADMIN_URL}?spotify_error=no_user_id")

            playlist = create_playlist_for_user(
                access_token=access_token,
                user_id=user_id,
                name=derived_playlist_title(),
                description=derived_playlist_description(),
            )
            playlist_id = playlist.get("id")
            if not playlist_id:
                return RedirectResponse(f"{FRONTEND_ADMIN_URL}?spotify_error=no_playlist_id")

            cfg.spotify_playlist_id = playlist_id
            db.add(cfg)
            db.commit()
            db.refresh(cfg)

        return RedirectResponse(f"{FRONTEND_ADMIN_URL}?spotify_connected=1")
    except (SpotifyAuthError, SpotifyApiError) as e:
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}?spotify_error={str(e)}")


# ---------- Public Spotify search (FE uses this) ----------

@app.get("/spotify/search")
def spotify_search(q: str, limit: int = 10, db: Session = Depends(get_db)):
    cfg = crud.get_playlist_config(db)
    if cfg is None or not cfg.spotify_refresh_token:
        raise HTTPException(status_code=400, detail="Playlist or Spotify connection is not fully configured.")

    try:
        access_token = get_valid_access_token(db, cfg)
        return search_tracks(access_token, q, limit=limit)
    except SpotifyAuthError as e:
        raise HTTPException(status_code=502, detail=f"Spotify auth error: {e}")
    except SpotifyApiError as e:
        raise HTTPException(status_code=502, detail=f"Spotify search error: {e}")


# ---------- Songs ----------

@app.get("/songs", response_model=list[schemas.SongOut])
def list_songs(db: Session = Depends(get_db)):
    return crud.list_songs(db)


@app.post("/songs", response_model=schemas.SongOut)
def create_song(song_in: schemas.SongCreate, db: Session = Depends(get_db)):
    # In a real platform you’d validate `user` and use a real identity.
    return add_song_to_app_playlist(db, song_in)
