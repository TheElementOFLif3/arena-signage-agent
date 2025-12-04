from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# =====================================================
# Country model
# =====================================================
class Country(Base):
    """
    Country configuration.

    - code: ISO country code (e.g. "US", "DE")
    - uses_fahrenheit: controls whether dashboards
      should render °F instead of °C for players in this country.
    """
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)

    # ISO code like "US", "DE" — UNIQUE
    code = Column(String(8), unique=True, index=True, nullable=False)

    # Human-readable country name
    name = Column(String(100), nullable=False)

    # Controls whether dashboard shows °F instead of °C
    uses_fahrenheit = Column(Boolean, default=False, nullable=False)

    # Relationship → players belonging to this country
    players = relationship("Player", back_populates="country")


# =====================================================
# PlayerGroup model  (group of players, e.g. "Lobby", "Food Court")
# =====================================================
class PlayerGroup(Base):
    """
    Logical group of players (e.g. "Lobby Screens", "Food Court").

    Used to assign group-level playlists which apply to all players
    in the group.
    """
    __tablename__ = "player_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)

    # Players that belong to this group
    players = relationship("Player", back_populates="group")

    # Playlists attached to this group
    group_playlists = relationship(
        "GroupPlaylist",
        back_populates="group",
        cascade="all, delete-orphan",
    )


# =====================================================
# Playlist model  (logical playlist, can be attached to player or group)
# =====================================================
class Playlist(Base):
    """
    A logical playlist which can be assigned to:
    - individual players (via PlayerPlaylist)
    - entire groups (via GroupPlaylist)
    """
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Items (slides / media entries) in this playlist
    items = relationship(
        "PlaylistItem",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistItem.order_index",
    )

    # Links to players and groups
    player_links = relationship(
        "PlayerPlaylist",
        back_populates="playlist",
        cascade="all, delete-orphan",
    )
    group_links = relationship(
        "GroupPlaylist",
        back_populates="playlist",
        cascade="all, delete-orphan",
    )


# =====================================================
# PlaylistItem model  (single slide / media in playlist)
# =====================================================
class PlaylistItem(Base):
    """
    Single media item (slide) inside a playlist.

    Could be an image, video, HTML page, etc.
    """
    __tablename__ = "playlist_items"

    id = Column(Integer, primary_key=True, index=True)

    playlist_id = Column(
        Integer,
        ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Human-readable title (e.g. "Burger Promo Slide")
    title = Column(String(150), nullable=True)

    # Path or URL to media (image, video, HTML page, etc.)
    media_url = Column(String(500), nullable=False)

    # How long this item should be shown (in seconds)
    duration_seconds = Column(Integer, nullable=True)

    # Order of items inside the playlist (0,1,2,...)
    order_index = Column(Integer, default=0, nullable=False)

    playlist = relationship("Playlist", back_populates="items")


# =====================================================
# Player model
# =====================================================
class Player(Base):
    """
    Physical playback device (Raspberry Pi / signage player).

    Stores hardware/network info and current status. Playlists can be
    attached directly, and/or inherited from its PlayerGroup.
    """
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)

    # ForeignKey → Country.code (NOT id)
    country_code = Column(String(8), ForeignKey("countries.code"), nullable=True)

    city = Column(String(100), nullable=True)
    arena_name = Column(String(150), nullable=True)

    resolution = Column(String(20), nullable=True)
    network_type = Column(String(20), nullable=True)

    # Always stored in °C internally
    temperature_c = Column(Integer, nullable=True)

    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, default=datetime.utcnow)

    # Optional group membership (one primary group per player for now)
    group_id = Column(Integer, ForeignKey("player_groups.id"), nullable=True)

    # Relationships
    country = relationship("Country", back_populates="players")
    group = relationship("PlayerGroup", back_populates="players")

    # Playlists attached directly to this player
    player_playlists = relationship(
        "PlayerPlaylist",
        back_populates="player",
        cascade="all, delete-orphan",
    )


# =====================================================
# PlayerPlaylist link  (playlist assigned to a specific player)
# =====================================================
class PlayerPlaylist(Base):
    """
    Many-to-many link between Player and Playlist.

    Represents a playlist explicitly assigned to a single player.
    """
    __tablename__ = "player_playlists"

    id = Column(Integer, primary_key=True, index=True)

    player_id = Column(
        Integer,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
    )
    playlist_id = Column(
        Integer,
        ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
    )

    # If a player has multiple playlists, this defines priority/order
    order_index = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    player = relationship("Player", back_populates="player_playlists")
    playlist = relationship("Playlist", back_populates="player_links")


# =====================================================
# GroupPlaylist link  (playlist assigned to a whole group)
# =====================================================
class GroupPlaylist(Base):
    """
    Many-to-many link between PlayerGroup and Playlist.

    All players in the group are considered to have these playlists
    (unless you later override logic on the player level).
    """
    __tablename__ = "group_playlists"

    id = Column(Integer, primary_key=True, index=True)

    group_id = Column(
        Integer,
        ForeignKey("player_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    playlist_id = Column(
        Integer,
        ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Order/priority of this playlist within the group
    order_index = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    group = relationship("PlayerGroup", back_populates="group_playlists")
    playlist = relationship("Playlist", back_populates="group_links")