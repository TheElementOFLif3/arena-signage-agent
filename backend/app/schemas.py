from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# =====================================================
# Country Schemas
# =====================================================
class CountryBase(BaseModel):
    """
    Base fields shared by all country schemas.

    - code: ISO country code, e.g., "US", "DE"
    - name: Human-readable country name
    - uses_fahrenheit: True for countries that prefer °F, otherwise °C
    """
    code: str
    name: str
    uses_fahrenheit: bool = False   # Controls °C / °F display for players


class CountryCreate(CountryBase):
    """Payload used when creating a new country."""
    pass


class CountryUpdate(BaseModel):
    """
    Payload used when partially updating a country.

    All fields are optional so PATCH-like updates are possible.
    """
    code: Optional[str] = None
    name: Optional[str] = None
    uses_fahrenheit: Optional[bool] = None


class CountryRead(CountryBase):
    """Country object returned in API responses."""
    id: int

    class Config:
        # Pydantic v2 replacement for legacy orm_mode=True
        from_attributes = True


# =====================================================
# Player Schemas
# =====================================================
class PlayerBase(BaseModel):
    """
    Base fields shared across all player schemas.

    - temperature_c is always stored in °C internally
      (conversion to °F happens at the presentation layer
       depending on the player's country).
    """
    device_id: str
    name: str

    country_code: Optional[str] = None   # Used for °C/°F selection
    city: Optional[str] = None
    arena_name: Optional[str] = None

    resolution: Optional[str] = None
    network_type: Optional[str] = None

    temperature_c: Optional[int] = None  # Always stored in °C internally
    is_online: Optional[bool] = False


class PlayerCreate(PlayerBase):
    """Payload used when creating a new player."""
    pass


class PlayerUpdate(BaseModel):
    """Payload used when partially updating a player."""
    name: Optional[str] = None
    country_code: Optional[str] = None
    city: Optional[str] = None
    arena_name: Optional[str] = None
    resolution: Optional[str] = None
    network_type: Optional[str] = None
    temperature_c: Optional[int] = None
    is_online: Optional[bool] = None


class PlayerRead(PlayerBase):
    """Full player representation returned in API responses."""
    id: int
    last_seen: datetime

    # Nested relationship to Country (may be null)
    country: Optional[CountryRead] = None

    class Config:
        from_attributes = True


# =====================================================
# Player Heartbeat Schema
# =====================================================
class PlayerHeartbeatUpdate(BaseModel):
    """
    Payload sent by a Raspberry Pi player on each heartbeat.

    - Server automatically updates `last_seen`.
    - `temperature_c` is optional and always transmitted in °C.
    - `is_online` defaults to True because heartbeat means "alive".
    - `network_type` describes connection type: wifi / ethernet / LTE / etc.
    """
    temperature_c: Optional[int] = None
    is_online: bool = True
    network_type: Optional[str] = None


# =====================================================
# Lightweight Player Status Schema  (used by dashboard)
# =====================================================
class PlayerStatus(BaseModel):
    """
    Lightweight player representation optimized for dashboard refresh.

    Only essential fields included for real-time monitoring.
    """
    id: int
    device_id: str
    name: str

    is_online: bool
    last_seen: datetime

    # Still stored in °C internally; UI decides whether to show °C or °F
    temperature_c: Optional[int] = None
    network_type: Optional[str] = None

    city: Optional[str] = None
    arena_name: Optional[str] = None

    # Needed for automatic °C / °F display in dashboard
    country_code: Optional[str] = None

    # Derived from the related Country (if any); default is False (°C).
    uses_fahrenheit: bool = False

    class Config:
        from_attributes = True


# =====================================================
# Playlist Item Schemas
# =====================================================
class PlaylistItemBase(BaseModel):
    """
    Base fields shared by all playlist item schemas.

    A playlist item represents a single media slide (image, video, HTML page, etc.).
    """
    title: Optional[str] = None              # Human readable title
    media_url: str                           # Path/URL to media asset
    duration_seconds: Optional[int] = None   # How long to show this item
    order_index: int = 0                     # Order inside the playlist (0,1,2,...)


class PlaylistItemCreate(PlaylistItemBase):
    """Payload used when creating a new playlist item."""
    playlist_id: int


class PlaylistItemUpdate(BaseModel):
    """
    Payload used when partially updating a playlist item.
    All fields are optional.
    """
    title: Optional[str] = None
    media_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    order_index: Optional[int] = None


class PlaylistItemRead(PlaylistItemBase):
    """Playlist item representation returned in API responses."""
    id: int
    playlist_id: int

    class Config:
        from_attributes = True


# =====================================================
# Playlist Schemas
# =====================================================
class PlaylistBase(BaseModel):
    """
    Base fields shared by all playlist schemas.

    A playlist is a logical list of media items that can be assigned
    to a player or to a player group.
    """
    name: str
    description: Optional[str] = None
    is_active: bool = True


class PlaylistCreate(PlaylistBase):
    """Payload used when creating a new playlist."""
    pass


class PlaylistUpdate(BaseModel):
    """
    Payload used when partially updating a playlist.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PlaylistRead(PlaylistBase):
    """Playlist representation returned in API responses."""
    id: int
    created_at: datetime
    updated_at: datetime

    # Nested playlist items ordered by `order_index`
    items: List[PlaylistItemRead] = []

    class Config:
        from_attributes = True


# =====================================================
# Player Group Schemas
# =====================================================
class PlayerGroupBase(BaseModel):
    """
    Base fields shared by all player group schemas.

    A player group is a logical grouping of players, e.g.:
    - "Lobby Screens"
    - "Food Court"
    - "Entrance TVs"
    """
    name: str
    description: Optional[str] = None


class PlayerGroupCreate(PlayerGroupBase):
    """Payload used when creating a new player group."""
    pass


class PlayerGroupUpdate(BaseModel):
    """
    Payload used when partially updating a player group.
    """
    name: Optional[str] = None
    description: Optional[str] = None


class PlayerGroupRead(PlayerGroupBase):
    """
    Player group representation returned in API responses.

    For now, players are not nested here to avoid heavy responses and
    circular references – they can be queried via a separate endpoint.
    """
    id: int

    class Config:
        from_attributes = True


# =====================================================
# PlayerPlaylist Schemas  (playlist assigned to a player)
# =====================================================
class PlayerPlaylistBase(BaseModel):
    """
    Base fields for a playlist assigned to a specific player.

    - order_index controls priority if a player has multiple playlists.
    """
    player_id: int
    playlist_id: int
    order_index: int = 0
    is_active: bool = True


class PlayerPlaylistCreate(PlayerPlaylistBase):
    """Payload used when creating a new player-playlist link."""
    pass


class PlayerPlaylistUpdate(BaseModel):
    """
    Payload used when partially updating a player-playlist link.
    """
    order_index: Optional[int] = None
    is_active: Optional[bool] = None


class PlayerPlaylistRead(PlayerPlaylistBase):
    """
    Representation of a playlist link attached to a player.

    Optionally includes a lightweight playlist object for convenience.
    """
    id: int
    # Optional nested playlist details (can be omitted in some endpoints)
    playlist: Optional[PlaylistRead] = None

    class Config:
        from_attributes = True


# =====================================================
# GroupPlaylist Schemas  (playlist assigned to a group)
# =====================================================
class GroupPlaylistBase(BaseModel):
    """
    Base fields for a playlist assigned to a player group.

    All players in the group can use these group-level playlists.
    """
    group_id: int
    playlist_id: int
    order_index: int = 0
    is_active: bool = True


class GroupPlaylistCreate(GroupPlaylistBase):
    """Payload used when creating a new group-playlist link."""
    pass


class GroupPlaylistUpdate(BaseModel):
    """
    Payload used when partially updating a group-playlist link.
    """
    order_index: Optional[int] = None
    is_active: Optional[bool] = None


class GroupPlaylistRead(GroupPlaylistBase):
    """
    Representation of a playlist link attached to a player group.

    Optionally includes a lightweight playlist object for convenience.
    """
    id: int
    playlist: Optional[PlaylistRead] = None
    group: Optional[PlayerGroupRead] = None

    class Config:
        from_attributes = True


# =====================================================
# Effective playlist for a player
# =====================================================
class EffectivePlaylistEntry(BaseModel):
    """
    One playlist entry in the effective playlist list for a player.

    - source: "player" (direct assignment) or "group" (via player group)
    - link_id: id of the PlayerPlaylist or GroupPlaylist link
    - order_index: ordering inside its source (player or group)
    - is_active: final active state (true only if link and playlist are active)
    - items: media items belonging to this playlist
    """
    playlist_id: int
    playlist_name: str

    source: str  # "player" or "group"
    link_id: int
    order_index: int = 0
    is_active: bool = True

    items: List[PlaylistItemRead] = []

    class Config:
        from_attributes = True


class EffectivePlaylistResponse(BaseModel):
    """
    Effective playlist definition for a player.

    - player_id: target player
    - group_id: player's group (if any)
    - entries: flattened list of playlist entries coming from
      both PlayerPlaylist and GroupPlaylist links.
      Entries are sorted so that "player" source comes first,
      then "group", each ordered by order_index.
    """
    player_id: int
    group_id: Optional[int] = None
    entries: List[EffectivePlaylistEntry] = []

    class Config:
        from_attributes = True


# =====================================================
# Player-facing playlist package for offline agents
# =====================================================
class PlaylistItemForPlayer(BaseModel):
    """
    Lightweight playlist item structure sent to the player agent.

    This structure is optimized for offline playback and caching:
      - media_url: final URL that the agent should download and cache
      - checksum: optional integrity check (hash, md5, sha256, etc.)
      - valid_from / valid_until: optional time window when the item is allowed
    """
    id: Optional[int] = None
    playlist_id: Optional[int] = None

    position: Optional[int] = 0
    media_type: Optional[str] = None

    duration_seconds: int
    media_url: str

    checksum: Optional[str] = None

    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class PlayerPlaylistPackage(BaseModel):
    """
    Complete playlist package for a single player, used by the offline agent.

    The player agent is expected to:
      - call the playlist endpoint
      - download/cache all media URLs
      - verify checksums if provided
      - store this package (JSON) locally as the current active playlist
    """
    player_id: int
    player_device_id: str

    playlist_id: Optional[int] = None
    playlist_name: Optional[str] = None
    playlist_updated_at: Optional[datetime] = None

    # Optional timezone information for local scheduling on the agent
    timezone: Optional[str] = None

    # Flat list of items to play in order
    items: List[PlaylistItemForPlayer]
    # =====================================================
# Player active playlist assignment
# =====================================================
class PlayerSetActivePlaylistRequest(BaseModel):
    """
    Payload used to set or clear the active playlist for a player.

    - playlist_id: target playlist id, or null to clear the active playlist.
    """
    playlist_id: Optional[int] = None