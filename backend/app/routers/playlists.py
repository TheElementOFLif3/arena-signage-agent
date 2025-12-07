from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from .. import models, schemas

router = APIRouter(
    prefix="/playlists",
    tags=["playlists"],
)

# =====================================================
# Helper functions
# =====================================================


def _get_playlist_or_404(playlist_id: int, db: Session) -> models.Playlist:
    """
    Load a playlist with its items or raise 404 if not found.
    """
    playlist = (
        db.query(models.Playlist)
        .options(joinedload(models.Playlist.items))
        .filter(models.Playlist.id == playlist_id)
        .first()
    )
    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found.",
        )
    return playlist


def _get_playlist_item_or_404(item_id: int, db: Session) -> models.PlaylistItem:
    """
    Load a playlist item or raise 404 if not found.
    """
    item = (
        db.query(models.PlaylistItem)
        .filter(models.PlaylistItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist item not found.",
        )
    return item


def _get_player_or_404(player_id: int, db: Session) -> models.Player:
    """
    Load a player or raise 404 if not found.
    """
    player = (
        db.query(models.Player)
        .filter(models.Player.id == player_id)
        .first()
    )
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found.",
        )
    return player


def _get_group_or_404(group_id: int, db: Session) -> models.PlayerGroup:
    """
    Load a player group or raise 404 if not found.
    """
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


def _get_player_playlist_link_or_404(
    link_id: int, db: Session
) -> models.PlayerPlaylist:
    """
    Load a player-playlist link with nested playlist + items or raise 404.
    """
    link = (
        db.query(models.PlayerPlaylist)
        .options(
            joinedload(models.PlayerPlaylist.playlist).joinedload(
                models.Playlist.items
            )
        )
        .filter(models.PlayerPlaylist.id == link_id)
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player-playlist link not found.",
        )
    return link


def _get_group_playlist_link_or_404(
    link_id: int, db: Session
) -> models.GroupPlaylist:
    """
    Load a group-playlist link with nested playlist + items + group or raise 404.
    """
    link = (
        db.query(models.GroupPlaylist)
        .options(
            joinedload(models.GroupPlaylist.playlist).joinedload(
                models.Playlist.items
            ),
            joinedload(models.GroupPlaylist.group),
        )
        .filter(models.GroupPlaylist.id == link_id)
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group-playlist link not found.",
        )
    return link


# =====================================================
# Effective playlist builder
# =====================================================


def _build_effective_playlist_for_player(
    player: models.Player,
    db: Session,
) -> List[schemas.EffectivePlaylistEntry]:
    """
    Build the effective playlist list for a given player.

    Source data:
      - PlayerPlaylist links (playlists assigned directly to the player)
      - GroupPlaylist links (playlists assigned to the player's group, if any)

    Rules:
      - Only include links where link.is_active == True
      - Only include playlists where playlist.is_active == True
      - Items are ordered by PlaylistItem.order_index
      - Final list is sorted:
          1) source "player" first, then "group"
          2) order_index ascending inside each source
    """
    entries: List[schemas.EffectivePlaylistEntry] = []

    # --- Player-level playlist links ---
    player_links = (
        db.query(models.PlayerPlaylist)
        .options(
            joinedload(models.PlayerPlaylist.playlist).joinedload(
                models.Playlist.items
            )
        )
        .filter(models.PlayerPlaylist.player_id == player.id)
        .all()
    )

    for link in player_links:
        if not link.is_active:
            continue
        playlist = link.playlist
        if not playlist or not playlist.is_active:
            continue

        items_sorted = sorted(
            playlist.items,
            key=lambda it: it.order_index if it.order_index is not None else 0,
        )

        entries.append(
            schemas.EffectivePlaylistEntry(
                playlist_id=playlist.id,
                playlist_name=playlist.name,
                source="player",
                link_id=link.id,
                order_index=link.order_index or 0,
                is_active=True,
                items=[
                    schemas.PlaylistItemRead.model_validate(it)
                    for it in items_sorted
                ],
            )
        )

    # --- Group-level playlist links (if the player is in a group) ---
    if player.group_id is not None:
        group_links = (
            db.query(models.GroupPlaylist)
            .options(
                joinedload(models.GroupPlaylist.playlist).joinedload(
                    models.Playlist.items
                )
            )
            .filter(models.GroupPlaylist.group_id == player.group_id)
            .all()
        )

        for link in group_links:
            if not link.is_active:
                continue
            playlist = link.playlist
            if not playlist or not playlist.is_active:
                continue

            items_sorted = sorted(
                playlist.items,
                key=lambda it: it.order_index if it.order_index is not None else 0,
            )

            entries.append(
                schemas.EffectivePlaylistEntry(
                    playlist_id=playlist.id,
                    playlist_name=playlist.name,
                    source="group",
                    link_id=link.id,
                    order_index=link.order_index or 0,
                    is_active=True,
                    items=[
                        schemas.PlaylistItemRead.model_validate(it)
                        for it in items_sorted
                    ],
                )
            )

    # Sort final entries: player playlists first, then group, each by order_index
    def sort_key(e: schemas.EffectivePlaylistEntry):
        source_weight = 0 if e.source == "player" else 1
        return (source_weight, e.order_index, e.playlist_id)

    entries.sort(key=sort_key)
    return entries


# =====================================================
# Playlist CRUD
# =====================================================


@router.post(
    "/",
    response_model=schemas.PlaylistRead,
    status_code=status.HTTP_201_CREATED,
)
def create_playlist(
    playlist_in: schemas.PlaylistCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new playlist (logical list of media items).
    """
    playlist = models.Playlist(
        name=playlist_in.name,
        description=playlist_in.description,
        is_active=playlist_in.is_active,
    )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return playlist


@router.get(
    "/",
    response_model=List[schemas.PlaylistRead],
)
def list_playlists(db: Session = Depends(get_db)):
    """
    List all playlists including their items (ordered by order_index).
    """
    playlists = (
        db.query(models.Playlist)
        .options(joinedload(models.Playlist.items))
        .all()
    )
    return playlists


@router.get(
    "/{playlist_id}",
    response_model=schemas.PlaylistRead,
)
def get_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a single playlist by ID (with items).
    """
    playlist = _get_playlist_or_404(playlist_id, db)
    return playlist


@router.put(
    "/{playlist_id}",
    response_model=schemas.PlaylistRead,
)
def update_playlist(
    playlist_id: int,
    playlist_in: schemas.PlaylistUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing playlist.

    Only fields that are provided in the request body will be updated.
    """
    playlist = _get_playlist_or_404(playlist_id, db)

    update_data = playlist_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(playlist, field, value)

    db.commit()
    db.refresh(playlist)
    return playlist


@router.delete(
    "/{playlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a playlist by ID.

    All related playlist items and links to players/groups
    are deleted via CASCADE.
    """
    playlist = (
        db.query(models.Playlist)
        .filter(models.Playlist.id == playlist_id)
        .first()
    )
    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found.",
        )

    db.delete(playlist)
    db.commit()
    return None


# =====================================================
# Playlist Items
# =====================================================


@router.post(
    "/{playlist_id}/items",
    response_model=schemas.PlaylistItemRead,
    status_code=status.HTTP_201_CREATED,
)
def add_item_to_playlist(
    playlist_id: int,
    item_in: schemas.PlaylistItemCreate,
    db: Session = Depends(get_db),
):
    """
    Add a new item (slide/media) to a playlist.

    Path param `playlist_id` is the source of truth – if the body
    contains a different playlist_id, a 400 error is returned.
    """
    playlist = _get_playlist_or_404(playlist_id, db)

    if item_in.playlist_id != playlist_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="playlist_id in body must match playlist_id in URL.",
        )

    item = models.PlaylistItem(
        playlist_id=playlist.id,
        title=item_in.title,
        media_url=item_in.media_url,
        duration_seconds=item_in.duration_seconds,
        order_index=item_in.order_index,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/{playlist_id}/items",
    response_model=List[schemas.PlaylistItemRead],
)
def list_playlist_items(
    playlist_id: int,
    db: Session = Depends(get_db),
):
    """
    List all items for a specific playlist ordered by `order_index`.
    """
    _ = _get_playlist_or_404(playlist_id, db)

    items = (
        db.query(models.PlaylistItem)
        .filter(models.PlaylistItem.playlist_id == playlist_id)
        .order_by(models.PlaylistItem.order_index.asc())
        .all()
    )
    return items


@router.put(
    "/items/{item_id}",
    response_model=schemas.PlaylistItemRead,
)
def update_playlist_item(
    item_id: int,
    item_in: schemas.PlaylistItemUpdate,
    db: Session = Depends(get_db),
):
    """
    Partially update an existing playlist item.
    """
    item = _get_playlist_item_or_404(item_id, db)

    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_playlist_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a single playlist item by ID.
    """
    item = _get_playlist_item_or_404(item_id, db)
    db.delete(item)
    db.commit()
    return None


# =====================================================
# Player ↔ Playlist links
# =====================================================


@router.post(
    "/player-links",
    response_model=schemas.PlayerPlaylistRead,
    status_code=status.HTTP_201_CREATED,
)
def create_player_playlist_link(
    link_in: schemas.PlayerPlaylistCreate,
    db: Session = Depends(get_db),
):
    """
    Assign a playlist to a specific player.

    - `player_id` and `playlist_id` must both exist.
    """
    _ = _get_player_or_404(link_in.player_id, db)
    playlist = _get_playlist_or_404(link_in.playlist_id, db)

    link = models.PlayerPlaylist(
        player_id=link_in.player_id,
        playlist_id=playlist.id,
        order_index=link_in.order_index,
        is_active=link_in.is_active,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.get(
    "/player-links/by-player/{player_id}",
    response_model=List[schemas.PlayerPlaylistRead],
)
def list_player_playlist_links(
    player_id: int,
    db: Session = Depends(get_db),
):
    """
    List all playlist links attached to a given player.

    Includes nested playlist + items for convenience.
    """
    _ = _get_player_or_404(player_id, db)

    links = (
        db.query(models.PlayerPlaylist)
        .options(
            joinedload(models.PlayerPlaylist.playlist).joinedload(
                models.Playlist.items
            )
        )
        .filter(models.PlayerPlaylist.player_id == player_id)
        .order_by(models.PlayerPlaylist.order_index.asc())
        .all()
    )
    return links


@router.put(
    "/player-links/{link_id}",
    response_model=schemas.PlayerPlaylistRead,
)
def update_player_playlist_link(
    link_id: int,
    link_in: schemas.PlayerPlaylistUpdate,
    db: Session = Depends(get_db),
):
    """
    Update properties of a player-playlist link (order_index, is_active).
    """
    link = _get_player_playlist_link_or_404(link_id, db)

    update_data = link_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(link, field, value)

    db.commit()
    db.refresh(link)
    return link


@router.delete(
    "/player-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_player_playlist_link(
    link_id: int,
    db: Session = Depends(get_db),
):
    """
    Remove a playlist assignment from a player.
    """
    link = (
        db.query(models.PlayerPlaylist)
        .filter(models.PlayerPlaylist.id == link_id)
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player-playlist link not found.",
        )

    db.delete(link)
    db.commit()
    return None


# =====================================================
# Group ↔ Playlist links
# =====================================================


@router.post(
    "/group-links",
    response_model=schemas.GroupPlaylistRead,
    status_code=status.HTTP_201_CREATED,
)
def create_group_playlist_link(
    link_in: schemas.GroupPlaylistCreate,
    db: Session = Depends(get_db),
):
    """
    Assign a playlist to an entire player group.
    """
    group = _get_group_or_404(link_in.group_id, db)
    playlist = _get_playlist_or_404(link_in.playlist_id, db)

    link = models.GroupPlaylist(
        group_id=group.id,
        playlist_id=playlist.id,
        order_index=link_in.order_index,
        is_active=link_in.is_active,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.get(
    "/group-links/by-group/{group_id}",
    response_model=List[schemas.GroupPlaylistRead],
)
def list_group_playlist_links(
    group_id: int,
    db: Session = Depends(get_db),
):
    """
    List all playlist links attached to a given group.

    Includes nested playlist (with items) and group info.
    """
    _ = _get_group_or_404(group_id, db)

    links = (
        db.query(models.GroupPlaylist)
        .options(
            joinedload(models.GroupPlaylist.playlist).joinedload(
                models.Playlist.items
            ),
            joinedload(models.GroupPlaylist.group),
        )
        .filter(models.GroupPlaylist.group_id == group_id)
        .order_by(models.GroupPlaylist.order_index.asc())
        .all()
    )
    return links


@router.put(
    "/group-links/{link_id}",
    response_model=schemas.GroupPlaylistRead,
)
def update_group_playlist_link(
    link_id: int,
    link_in: schemas.GroupPlaylistUpdate,
    db: Session = Depends(get_db),
):
    """
    Update properties of a group-playlist link (order_index, is_active).
    """
    link = _get_group_playlist_link_or_404(link_id, db)

    update_data = link_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(link, field, value)

    db.commit()
    db.refresh(link)
    return link


@router.delete(
    "/group-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_group_playlist_link(
    link_id: int,
    db: Session = Depends(get_db),
):
    """
    Remove a playlist assignment from a group.
    """
    link = (
        db.query(models.GroupPlaylist)
        .filter(models.GroupPlaylist.id == link_id)
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group-playlist link not found.",
        )

    db.delete(link)
    db.commit()
    return None


# =====================================================
# Effective playlist endpoint (for Pi agent)
# =====================================================


@router.get(
    "/effective/by-player/{player_id}",
    response_model=schemas.EffectivePlaylistResponse,
)
def get_effective_playlist_for_player(
    player_id: int,
    db: Session = Depends(get_db),
):
    """
    Return effective playlist definition for a given player.

    Combines:
      - PlayerPlaylist links (directly assigned playlists)
      - GroupPlaylist links (playlists assigned to the player's group)

    The Raspberry Pi agent can call this endpoint and iterate over `entries`
    to know exactly which slides to play, in which order.
    """
    player = _get_player_or_404(player_id, db)
    entries = _build_effective_playlist_for_player(player, db)

    return schemas.EffectivePlaylistResponse(
        player_id=player.id,
        group_id=player.group_id,
        entries=entries,
    )