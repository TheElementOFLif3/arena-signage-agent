#!/usr/bin/env python3
import os
import time
import socket
from typing import Optional, List, Dict, Any

import requests

# =====================================================
# Configuration
# =====================================================

# You can override this via environment variable ARENASIGNAGE_API_BASE_URL
API_BASE_URL = os.getenv("ARENASIGNAGE_API_BASE_URL", "http://localhost:8000")

DEVICE_ID = "raspi-001"
PLAYER_NAME = "Main Entrance Player"
COUNTRY_CODE = "US"
CITY = "Chicago"
ARENA_NAME = "United Center"
RESOLUTION = "1920x1080"
NETWORK_TYPE = "ethernet"

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL_SECONDS = 5

# How often to refresh effective playlists (seconds)
PLAYLIST_REFRESH_INTERVAL_SECONDS = 30


# =====================================================
# Helpers
# =====================================================

def get_cpu_temperature() -> Optional[int]:
    """
    Try to read CPU temperature in °C from Linux sysfs.

    On non-Raspberry Pi systems (e.g. macOS, dev machines) this will
    usually fail and return None.
    """
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            milli_c = int(f.read().strip())
            return int(milli_c / 1000)
    except Exception:
        return None


def detect_network_type() -> str:
    """
    Simple placeholder to detect network type.

    For now this just returns the configured NETWORK_TYPE constant.
    Later this could inspect interfaces (eth0, wlan0, etc.).
    """
    return NETWORK_TYPE


def api_get(path: str, **kwargs) -> requests.Response:
    """
    Small helper for GET requests to the backend.
    """
    url = f"{API_BASE_URL}{path}"
    return requests.get(url, timeout=5, **kwargs)


def api_post(path: str, json: dict | None = None, **kwargs) -> requests.Response:
    """
    Small helper for POST requests to the backend.
    """
    url = f"{API_BASE_URL}{path}"
    return requests.post(url, json=json, timeout=5, **kwargs)


# =====================================================
# Player registration + heartbeats
# =====================================================

def register_player() -> int:
    """
    Ensure this device is registered as a Player in the backend.

    1. Fetch all players from /players/
    2. If a player with our DEVICE_ID exists, reuse its id
    3. Otherwise create a new player via POST /players/
    """
    try:
        resp = api_get("/players/")
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to query players from backend: {e}") from e

    players: List[Dict[str, Any]] = resp.json()

    for p in players:
        if p.get("device_id") == DEVICE_ID:
            print(f"[INFO] Found existing player with id={p['id']}")
            return int(p["id"])

    payload = {
        "device_id": DEVICE_ID,
        "name": PLAYER_NAME,
        "country_code": COUNTRY_CODE,
        "city": CITY,
        "arena_name": ARENA_NAME,
        "resolution": RESOLUTION,
        "network_type": detect_network_type(),
        "temperature_c": get_cpu_temperature(),
        "is_online": True,
    }

    print("[INFO] Creating new player...")
    try:
        resp = api_post("/players/", json=payload)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to create player in backend: {e}") from e

    created = resp.json()
    print(f"[INFO] Created player with id={created['id']}")
    return int(created["id"])


def send_heartbeat(player_id: int) -> None:
    """
    Send periodic heartbeat to backend.

    Endpoint: POST /players/{player_id}/heartbeat
    Payload:
      - temperature_c  (°C)
      - is_online      (always True for now)
      - network_type   (wifi/ethernet/etc.)
    """
    payload = {
        "temperature_c": get_cpu_temperature(),
        "is_online": True,
        "network_type": detect_network_type(),
    }

    try:
        resp = api_post(f"/players/{player_id}/heartbeat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        print(
            f"[HB] Player {data['id']} OK | "
            f"online={data['is_online']} | "
            f"temp={data.get('temperature_c')}°C"
        )
    except Exception as e:
        print(f"[ERROR] Heartbeat failed: {e}")


# =====================================================
# Effective playlists (read-only from agent perspective)
# =====================================================

def fetch_effective_playlists(player_id: int) -> Dict[str, Any] | None:
    """
    Fetch the effective playlists for this player.

    Endpoint:
      GET /playlists/effective/by-player/{player_id}

    Expected JSON shape (based on schemas):
      {
        "player_id": int,
        "group_id": int | null,
        "entries": [
          {
            "playlist_id": int,
            "playlist_name": str,
            "source": "player" | "group",
            "link_id": int,
            "order_index": int,
            "is_active": bool,
            "items": [
              {
                "id": int,
                "playlist_id": int,
                "title": str | null,
                "media_url": str,
                "duration_seconds": int | null,
                "order_index": int
              },
              ...
            ]
          },
          ...
        ]
      }

    For now we only log the data. Later this will drive real playback logic.
    """
    try:
        resp = api_get(f"/playlists/effective/by-player/{player_id}")
        if resp.status_code == 404:
            print("[INFO] No effective playlists for this player yet.")
            return None
        resp.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Failed to fetch effective playlists for player {player_id}: {e}")
        return None

    data: Dict[str, Any] = resp.json()
    entries: List[Dict[str, Any]] = data.get("entries", [])

    if not entries:
        print("[INFO] Effective playlist is empty for this player.")
        return data

    print(
        f"[INFO] Effective playlists for player {data.get('player_id')} "
        f"(group_id={data.get('group_id')}): {len(entries)} entrie(s)"
    )

    for entry in entries:
        src = entry.get("source")
        pl_name = entry.get("playlist_name", "<unnamed>")
        order_index = entry.get("order_index", 0)
        items = entry.get("items", [])
        print(
            f"       - [{src}] '{pl_name}' order={order_index} items={len(items)}"
        )

    return data


# =====================================================
# Main loop
# =====================================================

def main() -> None:
    print("[INFO] ArenaSignage Pi agent starting...")
    print(f"[INFO] Hostname: {socket.gethostname()}")
    print(f"[INFO] Backend: {API_BASE_URL}")

    try:
        player_id = register_player()
    except RuntimeError as e:
        print(f"[FATAL] Could not register player: {e}")
        return

    print(f"[INFO] Using player_id={player_id}")

    # Initial effective playlist fetch (for debugging / inspection)
    fetch_effective_playlists(player_id)

    last_playlist_refresh = time.time()

    while True:
        send_heartbeat(player_id)

        # Periodically refresh effective playlists
        now = time.time()
        if now - last_playlist_refresh >= PLAYLIST_REFRESH_INTERVAL_SECONDS:
            fetch_effective_playlists(player_id)
            last_playlist_refresh = now

        time.sleep(HEARTBEAT_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()