"""Utility script to log the live local temperature every ten minutes."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional
import requests

# Closest station to west Santa Cruz (Garfield Park area)
STATION_ID = "KMRY"


def get_local_temperature() -> Optional[float]:
    """Fetch the current local temperature (°F) from the KE6AFE station."""
    headers = {"User-Agent": "Hot Tub Temp Logger (contact: hebardiansbehardians@gmail.com)"}
    try:
        obs_url = f"https://api.weather.gov/stations/{STATION_ID}/observations/latest"
        resp = requests.get(obs_url, headers=headers, timeout=10)
        resp.raise_for_status()
        props = resp.json()["properties"]
        temp_c = props["temperature"]["value"]
        if temp_c is None:
            return None
        temp_f = temp_c * 9 / 5 + 32
        return round(temp_f, 2)
    except Exception as exc:
        print(f"[WARN] Could not fetch live temperature: {exc}")
        return None


def log_local_temperature(interval_seconds: int = 600) -> None:
    """Log the local temperature every `interval_seconds` seconds."""
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        temperature = get_local_temperature()
        if temperature is not None:
            print(f"[{timestamp}] Live temperature: {temperature}°F")
        else:
            print(f"[{timestamp}] Live temperature: unavailable")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    log_local_temperature()