from __future__ import annotations

from functools import lru_cache
from typing import Dict, Any, Tuple

import requests
import openmeteo_requests
import requests_cache
from retry_requests import retry


# -----------------------------
# Open-Meteo client + caching
# -----------------------------
# Cache HTTP responses on disk for 1h to avoid API spam
# Use in-memory cache in Docker to avoid filesystem permission issues
_cache_session = requests_cache.CachedSession(
    backend="memory",
    expire_after=3600,
)
_retry_session = retry(_cache_session, retries=5, backoff_factor=0.2)

openmeteo = openmeteo_requests.Client(session=_retry_session)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


# ---- Small helper: geocode city -> (lat, lon, timezone) ----
@lru_cache(maxsize=128)
def geocode_city(city: str, country_code: str) -> Tuple[float, float, str | None]:
    """
    Resolve a (city, country_code) pair to latitude, longitude and timezone.

    Uses Open-Meteo's free geocoding API and caches results in-memory.
    """
    if not city or not country_code:
        raise ValueError("City and country_code are required for geocoding")

    params = {
        "name": city,
        "country": country_code,
        "count": 1,
        "language": "en",
        "format": "json",
    }
    resp = _retry_session.get(GEOCODE_URL, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results") or []
    if not results:
        raise ValueError(f"No geocoding results for {city}, {country_code}")

    r = results[0]
    lat = float(r["latitude"])
    lon = float(r["longitude"])
    timezone = r.get("timezone")
    return lat, lon, timezone


def _map_weather_code(code: int) -> str:
    """
    Very small mapping of WMO weather codes to a human-readable description.

    This is intentionally minimal – you can expand it later if you need more detail.
    """
    mapping = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        95: "Thunderstorm",
    }
    return mapping.get(code, f"Code {code}")


def get_current_weather(city: str, country_code: str) -> Dict[str, Any]:
    """
    Fetch current weather conditions for a city using Open-Meteo.

    - Geocodes (city, country_code) to lat/lon.
    - Calls the forecast API with `current` variables.
    - Returns a small normalized dict that the frontend can consume.
    """
    lat, lon, timezone = geocode_city(city, country_code)

    params = {
        "latitude": lat,
        "longitude": lon,
        # Order of variables must match the order we read them below
        "current": ["temperature_2m", "relative_humidity_2m", "weather_code"],
        "timezone": timezone or "auto",
    }

    responses = openmeteo.weather_api(FORECAST_URL, params=params)
    response = responses[0]

    current = response.Current()
    temp_c = current.Variables(0).Value()
    rel_humidity = current.Variables(1).Value()
    weather_code = int(current.Variables(2).Value())

    description = _map_weather_code(weather_code)

    return {
        "temp_c": temp_c,
        "humidity": rel_humidity,
        "weather_code": weather_code,
        "description": description,
        "time_utc": current.Time(),  # unix timestamp in seconds
        "latitude": response.Latitude(),
        "longitude": response.Longitude(),
    }