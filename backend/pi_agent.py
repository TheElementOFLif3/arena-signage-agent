#!/usr/bin/env python3
import os
import json
import time
import socket
from pathlib import Path
from typing import Optional, List, Dict, Any

from urllib.parse import urlparse

import requests

# =====================================================
# Config file handling
# =====================================================

CONFIG_PATH = Path(__file__).with_name("agent_config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "API_BASE_URL": "http://localhost:8000",
    "DEVICE_ID": "raspi-001",
    "PLAYER_NAME": "Main Entrance Player",
    "COUNTRY_CODE": "US",
    "CITY": "Chicago",
    "ARENA_NAME": "United Center",
    "RESOLUTION": "1920x1080",
    "NETWORK_TYPE": "ethernet",
    "HEARTBEAT_INTERVAL_SECONDS": 5,
    "PLAYLIST_REFRESH_INTERVAL_SECONDS": 30,
}

# Local cache layout
CACHE_ROOT = Path(__file__).with_name("cache")
PLAYLIST_PACKAGE_PATH = CACHE_ROOT / "playlist_package.json"
MEDIA_CACHE_DIR = CACHE_ROOT / "media"


def ensure_config_exists() -> None:
    """
    Ensure agent_config.json exists next to this script.

    If it does not exist, create one with DEFAULT_CONFIG and exit with
    a clear message so the user can run configure_agent.py.
    """
    if CONFIG_PATH.exists():
        return

    CONFIG_PATH.write_text(
        json.dumps(DEFAULT_CONFIG, indent=2),
        encoding="utf-8",
    )

    print("\n[WARNING] agent_config.json did not exist – a default one was created.")
    print("Please configure the agent before running it:")
    print("  python3 configure_agent.py\n")
    raise SystemExit(1)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from agent_config.json and apply sane defaults.

    Environment variable ARENASIGNAGE_API_BASE_URL overrides API_BASE_URL
    (useful for containers / testing).
    """
    ensure_config_exists()

    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[FATAL] Could not read agent_config.json: {exc}")
        raise SystemExit(1)

    # Start with defaults, then overlay values from file
    cfg: Dict[str, Any] = DEFAULT_CONFIG.copy()
    if isinstance(raw, dict):
        cfg.update(raw)

    # Optional override from environment
    api_override = os.getenv("ARENASIGNAGE_API_BASE_URL")
    if api_override:
        cfg["API_BASE_URL"] = api_override

    # Make sure timing values are ints
    for key in ("HEARTBEAT_INTERVAL_SECONDS", "PLAYLIST_REFRESH_INTERVAL_SECONDS"):
        try:
            cfg[key] = int(cfg.get(key, DEFAULT_CONFIG[key]))
        except (TypeError, ValueError):
            cfg[key] = DEFAULT_CONFIG[key]

    return cfg


# =====================================================
# Helper functions
# =====================================================

def ensure_cache_dirs() -> None:
    """
    Ensure local cache directories exist.
    """
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cpu_temperature() -> Optional[int]:
    """
    Try to read CPU temperature in °C from Linux sysfs.

    On non-Raspberry Pi systems this usually fails and returns None.
    """
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            milli_c = int(f.read().strip())
            return milli_c // 1000
    except Exception:
        return None


def detect_network_type(cfg: Dict[str, Any]) -> str:
    """
    Return the configured network type (ethernet/wifi/…).
    """
    return str(cfg.get("NETWORK_TYPE", "ethernet"))


def api_get(base_url: str, path: str, **kwargs) -> requests.Response:
    """
    Helper wrapper for GET requests to the backend.
    """
    return requests.get(f"{base_url}{path}", timeout=5, **kwargs)


def api_post(
    base_url: str,
    path: str,
    json: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> requests.Response:
    """
    Helper wrapper for POST requests to the backend.
    """
    return requests.post(f"{base_url}{path}", json=json, timeout=5, **kwargs)


# =====================================================
# Player registration & heartbeat logic
# =====================================================

def register_player(cfg: Dict[str, Any]) -> int:
    """
    Ensure this device is registered as a Player in the backend.

    Steps:
    1. Fetch all players via GET /players/
    2. If a player with the same DEVICE_ID exists, reuse its id
    3. Otherwise create a new player via POST /players/
    """
    base = cfg["API_BASE_URL"]

    try:
        resp = api_get(base, "/players/")
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Failed to query players from backend: {exc}") from exc

    players: List[Dict[str, Any]] = resp.json()

    # Check if a player with this device_id already exists
    for player in players:
        if player.get("device_id") == cfg["DEVICE_ID"]:
            pid = int(player["id"])
            print(f"[INFO] Found existing player with id={pid}")
            return pid

    # No existing player – create a new one
    payload = {
        "device_id": cfg["DEVICE_ID"],
        "name": cfg["PLAYER_NAME"],
        "country_code": cfg["COUNTRY_CODE"],
        "city": cfg["CITY"],
        "arena_name": cfg["ARENA_NAME"],
        "resolution": cfg["RESOLUTION"],
        "network_type": detect_network_type(cfg),
        "temperature_c": get_cpu_temperature(),
        "is_online": True,
    }

    print("[INFO] Creating new player in backend...")
    try:
        resp = api_post(base, "/players/", json=payload)
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Failed to create player in backend: {exc}") from exc

    created = resp.json()
    pid = int(created["id"])
    print(f"[INFO] Created new player with id={pid}")
    return pid


def send_heartbeat(cfg: Dict[str, Any], player_id: int) -> None:
    """
    Send a heartbeat update for this player.

    Endpoint: POST /players/{player_id}/heartbeat
    """
    base = cfg["API_BASE_URL"]

    payload = {
        "temperature_c": get_cpu_temperature(),
        "network_type": detect_network_type(cfg),
        "is_online": True,
    }

    try:
        resp = api_post(base, f"/players/{player_id}/heartbeat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        print(
            f"[HB] Player {data['id']} OK | "
            f"online={data.get('is_online')} | "
            f"temp={data.get('temperature_c')}°C"
        )
    except Exception as exc:
        print(f"[ERROR] Heartbeat failed: {exc}")


# =====================================================
# Playlist package sync & local cache (offline support)
# =====================================================

def _build_local_media_path(item: Dict[str, Any], index: int) -> Path:
    """
    Build a deterministic local path for a media file belonging to a playlist item.

    The filename is based on the original URL path plus a simple index prefix to
    avoid collisions when different items reference the same basename.
    """
    media_url = str(item.get("media_url", ""))
    parsed = urlparse(media_url)
    name = Path(parsed.path).name or f"item-{index}"

    # Ensure we have some reasonable name
    if not name:
        name = f"item-{index}"

    return MEDIA_CACHE_DIR / f"{index:04d}_{name}"


def download_media_for_playlist(package: Dict[str, Any]) -> Dict[str, Any]:
    """
    Download all media files referenced in the playlist package.

    For each item:
      - compute local path
      - skip download if file already exists
      - on success, store local_path on the item

    Returns the package with local_path fields attached to items.
    """
    ensure_cache_dirs()

    items: List[Dict[str, Any]] = package.get("items", [])
    if not items:
        print("[INFO] Playlist package has no items to download.")
        return package

    print(f"[INFO] Downloading media for {len(items)} playlist item(s)…")

    for idx, item in enumerate(items):
        media_url = item.get("media_url")
        if not media_url:
            print(f"[WARN] Item {idx} has no media_url, skipping.")
            continue

        local_path = _build_local_media_path(item, idx)

        # If the file already exists, reuse it
        if local_path.exists() and local_path.stat().st_size > 0:
            item["local_path"] = str(local_path)
            print(f"[CACHE] Using existing file for item {idx}: {local_path.name}")
            continue

        print(f"[DL] Item {idx}: {media_url} -> {local_path.name}")

        try:
            with requests.get(media_url, stream=True, timeout=15) as r:
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        except Exception as exc:
            print(f"[ERROR] Failed to download media for item {idx}: {exc}")
            # On failure, do not set local_path, so agent knows this item is not available
            continue

        item["local_path"] = str(local_path)

    return package


def fetch_playlist_package_from_server(cfg: Dict[str, Any], player_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch the PlayerPlaylistPackage from the backend.

    Endpoint:
      GET /players/{player_id}/playlist
    """
    base = cfg["API_BASE_URL"]

    try:
        resp = api_get(base, f"/players/{player_id}/playlist")
        if resp.status_code == 404:
            print("[INFO] No active playlist assigned to this player on the server.")
            return None
        resp.raise_for_status()
    except Exception as exc:
        print(f"[ERROR] Failed to fetch playlist package from server: {exc}")
        return None

    pkg: Dict[str, Any] = resp.json()
    print(
        f"[INFO] Received playlist package: "
        f"playlist_id={pkg.get('playlist_id')} "
        f"name={pkg.get('playlist_name')!r} "
        f"items={len(pkg.get('items', []))}"
    )
    return pkg


def save_local_playlist_package(package: Dict[str, Any]) -> None:
    """
    Persist the playlist package JSON to local cache.
    """
    ensure_cache_dirs()
    PLAYLIST_PACKAGE_PATH.write_text(
        json.dumps(package, indent=2),
        encoding="utf-8",
    )
    print(f"[INFO] Saved playlist package to {PLAYLIST_PACKAGE_PATH}")


def load_local_playlist_package() -> Optional[Dict[str, Any]]:
    """
    Load the last saved playlist package from local cache.

    Returns None if no package is available.
    """
    if not PLAYLIST_PACKAGE_PATH.exists():
        print("[INFO] No local playlist package found in cache.")
        return None

    try:
        pkg = json.loads(PLAYLIST_PACKAGE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERROR] Failed to read local playlist package: {exc}")
        return None

    items = pkg.get("items", [])
    print(
        f"[INFO] Loaded local playlist package: "
        f"playlist_id={pkg.get('playlist_id')} "
        f"name={pkg.get('playlist_name')!r} "
        f"items={len(items)}"
    )
    return pkg


def sync_playlist_with_server(cfg: Dict[str, Any], player_id: int) -> bool:
    """
    Synchronize the playlist package from the server and cache media locally.

    Returns True on success, False on failure (in which case the caller
    can fall back to using the last cached playlist).
    """
    pkg = fetch_playlist_package_from_server(cfg, player_id)
    if pkg is None:
        return False

    # Download media and attach local_path to package items
    pkg_with_files = download_media_for_playlist(pkg)

    # Save updated package to disk
    save_local_playlist_package(pkg_with_files)
    return True


def print_playlist_summary(package: Dict[str, Any]) -> None:
    """
    Print a short summary of the current playlist package.

    This function is a placeholder for real playback logic. For now it
    only shows which items are available and their local file paths.
    """
    items: List[Dict[str, Any]] = package.get("items", [])
    print(
        f"[PLAYLIST] Player {package.get('player_id')} | "
        f"Playlist {package.get('playlist_id')} "
        f"({package.get('playlist_name')!r}) | "
        f"items={len(items)}"
    )

    for idx, item in enumerate(items):
        local_path = item.get("local_path")
        status = "READY" if local_path and Path(local_path).exists() else "MISSING"
        print(
            f"  - #{idx:02d} type={item.get('media_type')} "
            f"duration={item.get('duration_seconds')}s "
            f"status={status} "
            f"path={local_path or '-'}"
        )


# =====================================================
# Main loop
# =====================================================

def main() -> None:
    cfg = load_config()
    ensure_cache_dirs()

    print("[INFO] ArenaSignage Agent starting…")
    print(f"[INFO] Hostname: {socket.gethostname()}")
    print(f"[INFO] Backend:  {cfg['API_BASE_URL']}")
    print(f"[INFO] Cache:    {CACHE_ROOT}")

    # Register / find player
    try:
        player_id = register_player(cfg)
    except RuntimeError as exc:
        print(f"[FATAL] {exc}")
        return

    print(f"[INFO] Using player_id={player_id}")

    # Initial attempt to sync playlist from server
    synced = sync_playlist_with_server(cfg, player_id)
    if not synced:
        print("[WARN] Initial playlist sync failed. Trying to use local cache.")
        local_pkg = load_local_playlist_package()
        if local_pkg:
            print_playlist_summary(local_pkg)
        else:
            print("[WARN] No playlist available yet (online or offline).")
    else:
        local_pkg = load_local_playlist_package()
        if local_pkg:
            print_playlist_summary(local_pkg)

    last_refresh = time.time()

    while True:
        # Send heartbeat (non-fatal on error)
        send_heartbeat(cfg, player_id)

        now = time.time()
        if now - last_refresh >= cfg["PLAYLIST_REFRESH_INTERVAL_SECONDS"]:
            print("[INFO] Running scheduled playlist sync…")
            synced = sync_playlist_with_server(cfg, player_id)
            if not synced:
                print("[WARN] Playlist sync failed; using last cached playlist if available.")
            local_pkg = load_local_playlist_package()
            if local_pkg:
                print_playlist_summary(local_pkg)
            last_refresh = now

        time.sleep(cfg["HEARTBEAT_INTERVAL_SECONDS"])


if __name__ == "__main__":
    main()