from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
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