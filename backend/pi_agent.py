#!/usr/bin/env python3
import os
import json
import time
import socket
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests

# =====================================================
# CONFIG LOADING
# =====================================================

CONFIG_PATH = Path(__file__).with_name("agent_config.json")

DEFAULT_CONFIG = {
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


def ensure_config_exists():
    """Create default agent_config.json if missing."""
    if not CONFIG_PATH.exists():
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)

        print("\n[WARNING] agent_config.json nije postojao — kreiran je default.")
        print("Molimo pokrenite konfiguraciju:")
        print("   python3 configure_agent.py\n")
        exit(1)


def load_config() -> Dict[str, Any]:
    ensure_config_exists()

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"[FATAL] Ne mogu da učitam agent_config.json: {e}")
        exit(1)

    # ENV override (npr. ARENASIGNAGE_API_BASE_URL)
    api_override = os.getenv("ARENASIGNAGE_API_BASE_URL")
    if api_override:
        config["API_BASE_URL"] = api_override

    return config


# =====================================================
# UTIL FUNKCIJE
# =====================================================

def get_cpu_temperature() -> Optional[int]:
    """Read CPU temp on Linux."""

    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            milli_c = int(f.read().strip())
            return milli_c // 1000
    except:
        return None


def detect_network_type(cfg: dict) -> str:
    return cfg.get("NETWORK_TYPE", "ethernet")


def api_get(base: str, path: str, **kwargs):
    return requests.get(base + path, timeout=5, **kwargs)


def api_post(base: str, path: str, json=None, **kwargs):
    return requests.post(base + path, json=json, timeout=5, **kwargs)


# =====================================================
# PLAYER LOGIKA
# =====================================================

def register_player(cfg: dict) -> int:
    base = cfg["API_BASE_URL"]

    try:
        resp = api_get(base, "/players/")
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to query players: {e}") from e

    players = resp.json()

    # Da li već postoji?
    for p in players:
        if p["device_id"] == cfg["DEVICE_ID"]:
            print(f"[INFO] Found existing player id={p['id']}")
            return p["id"]

    # Nema → kreiraj
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

    print("[INFO] Creating new player...")
    try:
        resp = api_post(base, "/players/", json=payload)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to create player: {e}") from e

    created = resp.json()
    print(f"[INFO] Created new player id={created['id']}")
    return created["id"]


def send_heartbeat(cfg: dict, player_id: int):
    base = cfg["API_BASE_URL"]

    payload = {
        "temperature_c": get_cpu_temperature(),
        "network_type": detect_network_type(cfg),
        "is_online": True,
    }

    try:
        resp = api_post(base, f"/players/{player_id}/heartbeat", json=payload)
        resp.raise_for_status()
        info = resp.json()
        print(f"[HB] Player {info['id']} | temp={info.get('temperature_c')}°C")
    except Exception as e:
        print(f"[ERROR] Heartbeat failed: {e}")


def fetch_effective_playlists(cfg: dict, player_id: int):
    base = cfg["API_BASE_URL"]

    try:
        resp = api_get(base, f"/playlists/effective/by-player/{player_id}")
        if resp.status_code == 404:
            print("[INFO] No playlist yet.")
            return
        resp.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Playlist fetch failed: {e}")
        return

    data = resp.json()
    entries = data.get("entries", [])
    print(f"[INFO] Effective playlist entries={len(entries)}")
    for e in entries:
        print(f"   - {e.get('playlist_name')} ({len(e.get('items', []))} items)")


# =====================================================
# MAIN
# =====================================================

def main():
    cfg = load_config()

    print("[INFO] ArenaSignage Agent")
    print(f"[INFO] Host: {socket.gethostname()}")
    print(f"[INFO] API:  {cfg['API_BASE_URL']}")

    # Register or find player
    try:
        player_id = register_player(cfg)
    except RuntimeError as e:
        print(f"[FATAL] {e}")
        return

    print(f"[INFO] Active player_id={player_id}")
    fetch_effective_playlists(cfg, player_id)

    last_refresh = time.time()

    while True:
        send_heartbeat(cfg, player_id)

        if time.time() - last_refresh >= cfg["PLAYLIST_REFRESH_INTERVAL_SECONDS"]:
            fetch_effective_playlists(cfg, player_id)
            last_refresh = time.time()

        time.sleep(cfg["HEARTBEAT_INTERVAL_SECONDS"])


if __name__ == "__main__":
    main()