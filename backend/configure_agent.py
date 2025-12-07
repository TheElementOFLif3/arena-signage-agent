#!/usr/bin/env python3
import json
from pathlib import Path

from pi_agent import CONFIG_PATH, DEFAULT_CONFIG  # reuse shared defaults


def prompt(prompt_text: str, default: str) -> str:
    """
    Ask user for a value; if input is empty, return the default.
    """
    raw = input(f"{prompt_text} [{default}]: ").strip()
    return raw or default


def main() -> None:
    print("=== ArenaSignage Agent configuration ===")

    # Load existing config if present, otherwise start from defaults
    current = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.is_file():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                current.update(existing)
        except Exception as exc:
            print(f"[WARN] Failed to read existing config: {exc}")
            print("[WARN] Using defaults instead.")

    print(f"\nConfig file: {CONFIG_PATH}\n")

    cfg: dict = {}
    cfg["API_BASE_URL"] = prompt(
        "Backend URL (FastAPI server)",
        current["API_BASE_URL"],
    )
    cfg["DEVICE_ID"] = prompt("Device ID (unique code)", current["DEVICE_ID"])
    cfg["PLAYER_NAME"] = prompt("Player name", current["PLAYER_NAME"])
    cfg["COUNTRY_CODE"] = prompt(
        "Country code (e.g. US, RS)",
        current["COUNTRY_CODE"],
    )
    cfg["CITY"] = prompt("City", current["CITY"])
    cfg["ARENA_NAME"] = prompt("Arena / venue name", current["ARENA_NAME"])
    cfg["RESOLUTION"] = prompt(
        "Screen resolution (e.g. 1920x1080)",
        current["RESOLUTION"],
    )
    cfg["NETWORK_TYPE"] = prompt(
        "Network type (ethernet/wifi)",
        current["NETWORK_TYPE"],
    )

    hb_default = str(current["HEARTBEAT_INTERVAL_SECONDS"])
    hb_input = prompt("Heartbeat interval in seconds", hb_default)
    try:
        cfg["HEARTBEAT_INTERVAL_SECONDS"] = int(hb_input)
    except ValueError:
        print("[WARN] Invalid heartbeat value, keeping previous/default.")
        cfg["HEARTBEAT_INTERVAL_SECONDS"] = current["HEARTBEAT_INTERVAL_SECONDS"]

    pl_default = str(current["PLAYLIST_REFRESH_INTERVAL_SECONDS"])
    pl_input = prompt("Playlist refresh interval in seconds", pl_default)
    try:
        cfg["PLAYLIST_REFRESH_INTERVAL_SECONDS"] = int(pl_input)
    except ValueError:
        print("[WARN] Invalid playlist refresh value, keeping previous/default.")
        cfg["PLAYLIST_REFRESH_INTERVAL_SECONDS"] = current[
            "PLAYLIST_REFRESH_INTERVAL_SECONDS"
        ]

    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"\n[OK] Configuration saved to {CONFIG_PATH}")
    print("You can now start the agent with:\n")
    print("  source venv/bin/activate")
    print("  python3 pi_agent.py\n")


if __name__ == "__main__":
    main()