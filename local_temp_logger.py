"""Utility script to log the local temperature every ten minutes."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import requests

# Weather API Configuration for Santa Cruz, CA (zip 95060)
LATITUDE = 36.974
LONGITUDE = -122.031


def get_local_temperature() -> Optional[float]:
    """Fetch the current local temperature in Fahrenheit.

    Uses the National Weather Service API which does not require an API key.
    Returns ``None`` if the temperature cannot be retrieved.
    """
    headers = {"User-Agent": "Hot Tub Temp Logger (contact: hebardiansbehardians@gmail.com)"}

    try:
        point_url = f"https://api.weather.gov/points/{LATITUDE},{LONGITUDE}"
        point_response = requests.get(point_url, headers=headers, timeout=10)
        point_response.raise_for_status()
        forecast_url = point_response.json()["properties"]["forecastHourly"]

        forecast_response = requests.get(forecast_url, headers=headers, timeout=10)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        current_temp_f = forecast_data["properties"]["periods"][0]["temperature"]
        return round(float(current_temp_f), 2)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"[WARN] Could not fetch local temperature: {exc}")
        return None


def log_local_temperature(interval_seconds: int = 600) -> None:
    """Log the local temperature every ``interval_seconds`` seconds."""
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        temperature = get_local_temperature()
        if temperature is not None:
            print(f"[{timestamp}] Local temperature: {temperature}°F")
        else:
            print(f"[{timestamp}] Local temperature: unavailable")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    log_local_temperature()
