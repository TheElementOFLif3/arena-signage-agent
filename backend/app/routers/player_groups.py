from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models, schemas

router = APIRouter(
    prefix="/player-groups",
    tags=["player-groups"],
)


# =====================================================
# Helper: load group or raise 404
# =====================================================
def _get_group_or_404(group_id: int, db: Session) -> models.PlayerGroup:
    group = (
        db.query(models.PlayerGroup)
        .filter(models.PlayerGroup.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player group not found.",
        )
    return group


# =====================================================
# PlayerGroup CRUD
# =====================================================
@router.post(
    "/",
    response_model=schemas.PlayerGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_player_group(
    group_in: schemas.PlayerGroupCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new player group (e.g. 'Lobby Screens', 'Food Court').
    """
    # Optional: enforce unique name at application level
    existing = (
        db.query(models.PlayerGroup)
        .filter(models.PlayerGroup.name == group_in.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A player group with this name already exists.",
        )

    group = models.PlayerGroup(
        name=group_in.name,
        description=group_in.description,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get(
    "/",
    response_model=List[schemas.PlayerGroupRead],
)
def list_player_groups(db: Session = Depends(get_db)):
    """
    List all player groups.
    """
    groups = db.query(models.PlayerGroup).order_by(models.PlayerGroup.name.asc()).all()
    return groups


@router.get(
    "/{group_id}",
    response_model=schemas.PlayerGroupRead,
)
def get_player_group(
    group_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a single player group by ID.
    """
    group = _get_group_or_404(group_id, db)
    return group


@router.put(
    "/{group_id}",
    response_model=schemas.PlayerGroupRead,
)
def update_player_group(
    group_id: int,
    group_in: schemas.PlayerGroupUpdate,
    db: Session = Depends(get_db),
):
    """
    Partially update an existing player group.

    Only fields that are provided in the request body will be updated.
    """
    group = _get_group_or_404(group_id, db)

    update_data = group_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)

    db.commit()
    db.refresh(group)
    return group


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_player_group(
    group_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a player group by ID.

    Players with this group_id will keep their records,
    but their group_id will be set to NULL by the database
    if you configure ON DELETE SET NULL, or you can handle
    that manually if needed.
    """
    group = _get_group_or_404(group_id, db)

    db.delete(group)
    db.commit()
    return None


# =====================================================
# Convenience: list players in a group
# =====================================================
@router.get(
    "/{group_id}/players",
    response_model=List[schemas.PlayerRead],
)
def list_players_in_group(
    group_id: int,
    db: Session = Depends(get_db),
):
    """
    List all players that belong to the given group.
    """
    _ = _get_group_or_404(group_id, db)

    players = (
        db.query(models.Player)
        .filter(models.Player.group_id == group_id)
        .order_by(models.Player.name.asc())
        .all()
    )
    return players