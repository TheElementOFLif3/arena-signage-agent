from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from ..weather_service import get_current_weather
from .. import models, schemas
from ..db import get_db

# Main router for /players
router = APIRouter(prefix="/players", tags=["players"])


# ------------------------------------------------------------------
# Internal helper: Convert SQLAlchemy Player -> PlayerStatus
# ------------------------------------------------------------------
def _to_player_status(player: models.Player) -> schemas.PlayerStatus:
    """
    Create a lightweight PlayerStatus structure from ORM Player.
    Includes a flag indicating whether the country uses Fahrenheit.
    """
    uses_f = False
    if player.country is not None:
        uses_f = bool(getattr(player.country, "uses_fahrenheit", False))

    return schemas.PlayerStatus(
        id=player.id,
        device_id=player.device_id,
        name=player.name,
        is_online=player.is_online,
        last_seen=player.last_seen,
        temperature_c=player.temperature_c,
        network_type=player.network_type,
        city=player.city,
        arena_name=player.arena_name,
        country_code=player.country_code,
        uses_fahrenheit=uses_f,
    )


# ------------------------------------------------------------------
# Internal helper: Build offline-ready playlist package for a player
# ------------------------------------------------------------------
def _build_playlist_package(
    player: models.Player,
    request: Request,
) -> schemas.PlayerPlaylistPackage:
    """
    Build a structured playlist package for a given player.

    The package is designed for offline caching on the player agent:
      - active playlist assigned to this player
      - ordered list of items with ready-to-use media URLs
      - metadata for integrity checks and scheduling

    Expected model structure (adjust to your actual models if needed):

      - player.active_playlist -> models.Playlist or None
      - playlist.items         -> List[models.PlaylistItem]
      - item.media             -> models.Media (image/video/pdf/url...)
    """
    active_playlist = getattr(player, "active_playlist", None)
    if active_playlist is None:
        raise HTTPException(
            status_code=404,
            detail="No active playlist assigned to this player.",
        )

    # Base URL of the API (e.g., https://server/api)
    base_url = str(request.base_url).rstrip("/")

    items_payload: List[schemas.PlaylistItemForPlayer] = []

    # Assume active_playlist.items is already ordered
    for item in getattr(active_playlist, "items", []):
        media = getattr(item, "media", None)

        # If there is no associated media object, fallback to legacy media_url
        media_url: Optional[str] = None
        if media is not None:
            media_url = getattr(media, "public_url", None) or getattr(
                media, "file_path", None
            )

        # If there is no media or no URL from media, use the item's media_url
        if not media_url:
            media_url = getattr(item, "media_url", None)

        # If there is still no URL, fallback to an API-based download endpoint
        if not media_url and media is not None:
            media_id = getattr(media, "id", None)
            if media_id is not None:
                media_url = f"{base_url}/media/{media_id}/file"

        # If we still do not have a URL, skip this item
        if not media_url:
            continue

        # Checksum or hash for integrity verification on the agent
        checksum = None
        if media is not None:
            checksum = getattr(media, "checksum", None)

        # Media type (IMAGE/VIDEO/PDF/URL/HTML...)
        media_type = None
        if media is not None:
            media_type = getattr(media, "media_type", None)

        # Duration for displaying/playing this item
        duration_seconds = (
            getattr(item, "duration_seconds", None)
            or (getattr(media, "default_duration", None) if media is not None else None)
            or 10
        )

        # Ordering/position of the item within the playlist
        position = getattr(item, "order_index", None)

        valid_from = getattr(item, "valid_from", None) if hasattr(item, "valid_from") else None
        valid_until = getattr(item, "valid_until", None) if hasattr(item, "valid_until") else None

        items_payload.append(
            schemas.PlaylistItemForPlayer(
                id=getattr(item, "id", None),
                playlist_id=getattr(active_playlist, "id", None),
                position=position,
                media_type=media_type,
                duration_seconds=duration_seconds,
                media_url=media_url,
                checksum=checksum,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        )

    if not items_payload:
        # No usable items in the active playlist
        raise HTTPException(
            status_code=404,
            detail="Active playlist has no playable items for this player.",
        )

    return schemas.PlayerPlaylistPackage(
        player_id=player.id,
        player_device_id=player.device_id,
        playlist_id=getattr(active_playlist, "id", None),
        playlist_name=getattr(active_playlist, "name", None),
        playlist_updated_at=getattr(active_playlist, "updated_at", None),
        timezone=getattr(player, "timezone", None),
        items=items_payload,
    )


# ------------------------------------------------------------------
# Create a new player
# ------------------------------------------------------------------
@router.post(
    "/",
    response_model=schemas.PlayerRead,
    status_code=status.HTTP_201_CREATED,
)
def create_player(player_in: schemas.PlayerCreate, db: Session = Depends(get_db)):
    """
    Register a new player (Raspberry Pi signage device).
    Ensures device_id is unique.
    """
    existing = (
        db.query(models.Player)
        .filter(models.Player.device_id == player_in.device_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="A player with this device_id already exists.",
        )

    player = models.Player(**player_in.model_dump())
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


# ------------------------------------------------------------------
# List all players
# ------------------------------------------------------------------
@router.get("/", response_model=List[schemas.PlayerRead])
def list_players(db: Session = Depends(get_db)):
    """
    Return all registered players including related Country info.
    """
    players = (
        db.query(models.Player)
        .options(joinedload(models.Player.country))
        .all()
    )
    return players


# ------------------------------------------------------------------
# Status endpoints (must come before /{player_id})
# ------------------------------------------------------------------
@router.get("/status", response_model=List[schemas.PlayerStatus])
def list_player_statuses(db: Session = Depends(get_db)):
    """
    Return compact live status for all players.
    """
    players = (
        db.query(models.Player)
        .options(joinedload(models.Player.country))
        .all()
    )
    return [_to_player_status(p) for p in players]


@router.get("/status/online", response_model=List[schemas.PlayerStatus])
def list_online_players(db: Session = Depends(get_db)):
    """
    Return all players currently marked as online.
    """
    players = (
        db.query(models.Player)
        .options(joinedload(models.Player.country))
        .filter(models.Player.is_online.is_(True))
        .all()
    )
    return [_to_player_status(p) for p in players]


@router.get("/status/offline", response_model=List[schemas.PlayerStatus])
def list_offline_players(db: Session = Depends(get_db)):
    """
    Return all players marked as offline.
    """
    players = (
        db.query(models.Player)
        .options(joinedload(models.Player.country))
        .filter(models.Player.is_online.is_(False))
        .all()
    )
    return [_to_player_status(p) for p in players]


# ------------------------------------------------------------------
# Get a single player
# ------------------------------------------------------------------
@router.get("/{player_id}", response_model=schemas.PlayerRead)
def get_player(player_id: int, db: Session = Depends(get_db)):
    """
    Return a player by its numeric ID.
    """
    player = (
        db.query(models.Player)
        .options(joinedload(models.Player.country))
        .filter(models.Player.id == player_id)
        .first()
    )
    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")
    return player


# ------------------------------------------------------------------
# Update a player
# ------------------------------------------------------------------
@router.put("/{player_id}", response_model=schemas.PlayerRead)
def update_player(
    player_id: int,
    player_in: schemas.PlayerUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing player.
    Only fields provided will be modified.
    """
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")

    for field, value in player_in.model_dump(exclude_unset=True).items():
        setattr(player, field, value)

    db.commit()
    db.refresh(player)
    return player


# ------------------------------------------------------------------
# Delete a player
# ------------------------------------------------------------------
@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_player(player_id: int, db: Session = Depends(get_db)):
    """
    Remove a player by ID.
    """
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")

    db.delete(player)
    db.commit()
    return None


# ------------------------------------------------------------------
# Heartbeat
# ------------------------------------------------------------------
@router.post("/{player_id}/heartbeat", response_model=schemas.PlayerRead)
def heartbeat_player(
    player_id: int,
    heartbeat_in: schemas.PlayerHeartbeatUpdate,
    db: Session = Depends(get_db),
):
    """
    Heartbeat from the player device.
    Updates last_seen and optional status values.
    """
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")

    player.last_seen = datetime.utcnow()

    if heartbeat_in.temperature_c is not None:
        player.temperature_c = heartbeat_in.temperature_c
    if heartbeat_in.network_type is not None:
        player.network_type = heartbeat_in.network_type
    if heartbeat_in.is_online is not None:
        player.is_online = heartbeat_in.is_online

    db.commit()
    db.refresh(player)
    return player


# ------------------------------------------------------------------
# Playlist package for a player (for offline sync)
# ------------------------------------------------------------------
@router.get(
    "/{player_id}/playlist",
    response_model=schemas.PlayerPlaylistPackage,
)
def get_player_playlist_package(
    player_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Return a fully-prepared playlist package for the given player.

    The player agent should:
      - call this endpoint when online
      - download all referenced media URLs and verify checksums
      - store the result locally (JSON + media files)
      - always play from the local cache, using this endpoint only for sync/updates
    """
    player = (
        db.query(models.Player)
        .options(
            joinedload(models.Player.country),
            joinedload(models.Player.active_playlist).joinedload(
                models.Playlist.items
            ).joinedload(models.PlaylistItem.media),
        )
        .filter(models.Player.id == player_id)
        .first()
    )

    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")

    return _build_playlist_package(player, request)


# ------------------------------------------------------------------
# Weather for a player
# ------------------------------------------------------------------
@router.get("/{player_id}/weather")
def get_player_weather(player_id: int, db: Session = Depends(get_db)):
    """
    Return local weather for the player's configured city/country.
    """
    player = (
        db.query(models.Player)
        .options(joinedload(models.Player.country))
        .filter(models.Player.id == player_id)
        .first()
    )

    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")

    if not player.city or not player.country_code:
        raise HTTPException(
            status_code=400,
            detail="City and country_code are required for weather lookup.",
        )

    uses_f = False
    if player.country is not None:
        uses_f = bool(getattr(player.country, "uses_fahrenheit", False))

    try:
        weather_raw = get_current_weather(player.city, player.country_code)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Weather service error: {exc}",
        )

    temp_c = weather_raw.get("temp_c")
    temp_display = temp_c if not uses_f else round(temp_c * 9 / 5 + 32, 1)
    unit = "F" if uses_f else "C"

    return {
        "player_id": player.id,
        "city": player.city,
        "country_code": player.country_code,
        "uses_fahrenheit": uses_f,
        "weather": {
            **weather_raw,
            "temp_display": temp_display,
            "temp_unit": unit,
        },
    }


# ------------------------------------------------------------------
# Set or clear active playlist for a player
# ------------------------------------------------------------------
@router.put(
    "/{player_id}/active-playlist",
    response_model=schemas.PlayerRead,
)
def set_player_active_playlist(
    player_id: int,
    payload: schemas.PlayerSetActivePlaylistRequest,
    db: Session = Depends(get_db),
):
    """
    Set or clear the active playlist for a player.

    - If playlist_id is provided, it must exist.
    - If playlist_id is null, active_playlist_id is cleared.
    """
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")

    if payload.playlist_id is None:
        # Clear active playlist
        player.active_playlist_id = None
    else:
        playlist = (
            db.query(models.Playlist)
            .filter(models.Playlist.id == payload.playlist_id)
            .first()
        )
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found.")

        # Optionally you can enforce that the playlist is active:
        # if not playlist.is_active:
        #     raise HTTPException(
        #         status_code=400,
        #         detail="Playlist is not active.",
        #     )

        player.active_playlist_id = playlist.id

    db.commit()
    db.refresh(player)
    return player