#!/usr/bin/env python3
import json

from pi_agent import CONFIG_PATH, DEFAULT_CONFIG  # reuse from pi_agent.py


def prompt(prompt_text: str, default: str) -> str:
    """
    Ask user for a value; if empty input, return default.
    """
    raw = input(f"{prompt_text} [{default}]: ").strip()
    return raw or default


def main() -> None:
    print("=== ArenaSignage Agent configuration ===")

    # Load existing config if present, otherwise use defaults
    current = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.is_file():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                existing = json.load(f)
            current.update(existing)
        except Exception as exc:
            print(f"[WARN] Failed to read existing config: {exc}")
            print("[WARN] Using defaults instead.")

    print(f"\nConfig file: {CONFIG_PATH}\n")

    cfg: dict = {}

    cfg["API_BASE_URL"] = prompt(
        "Backend URL (FastAPI server)", current["API_BASE_URL"]
    )
    cfg["DEVICE_ID"] = prompt(
        "Device ID (unique code)", current["DEVICE_ID"]
    )
    cfg["PLAYER_NAME"] = prompt(
        "Player name", current["PLAYER_NAME"]
    )
    cfg["COUNTRY_CODE"] = prompt(
        "Country code (e.g. US, RS)", current["COUNTRY_CODE"]
    )
    cfg["CITY"] = prompt(
        "City", current["CITY"]
    )
    cfg["ARENA_NAME"] = prompt(
        "Arena / venue name", current["ARENA_NAME"]
    )
    cfg["RESOLUTION"] = prompt(
        "Screen resolution (e.g. 1920x1080)", current["RESOLUTION"]
    )
    cfg["NETWORK_TYPE"] = prompt(
        "Network type (ethernet/wifi)", current["NETWORK_TYPE"]
    )

    # Heartbeat interval
    hb_default = str(current["HEARTBEAT_INTERVAL_SECONDS"])
    hb_value = prompt("Heartbeat interval in seconds", hb_default)
    try:
        cfg["HEARTBEAT_INTERVAL_SECONDS"] = int(hb_value)
    except ValueError:
        print("[WARN] Invalid heartbeat value, keeping default.")
        cfg["HEARTBEAT_INTERVAL_SECONDS"] = current["HEARTBEAT_INTERVAL_SECONDS"]

    # Playlist refresh interval
    pl_default = str(current["PLAYLIST_REFRESH_INTERVAL_SECONDS"])
    pl_value = prompt("Playlist refresh interval in seconds", pl_default)
    try:
        cfg["PLAYLIST_REFRESH_INTERVAL_SECONDS"] = int(pl_value)
    except ValueError:
        print("[WARN] Invalid playlist refresh value, keeping default.")
        cfg["PLAYLIST_REFRESH_INTERVAL_SECONDS"] = current[
            "PLAYLIST_REFRESH_INTERVAL_SECONDS"
        ]

    # Save to JSON
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"\n[OK] Configuration saved to {CONFIG_PATH}")
    print("You can now start the agent with:\n")
    print("  source venv/bin/activate")
    print("  python3 pi_agent.py\n")


if __name__ == "__main__":
    main()