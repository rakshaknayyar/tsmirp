"""Daily weather for the demo area: Open-Meteo historical archive, with a fallback.

- Source: https://archive-api.open-meteo.com (free, no key). The download is cached under
  ml/data/raw/, so later runs are offline and reproducible.
- If the API cannot be reached (or source="fallback" is asked for, e.g. in tests), an
  APPROXIMATE monthly climate table is used instead (app/ml/risk_features.py). The report
  always says which source was used.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import httpx

from app.ml.risk_features import CITY_CENTRE, fallback_weather

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
Weather = dict[date, tuple[float, float]]  # day -> (rain_mm, temp_max_c)


def _days(start: date, n_days: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n_days)]


def fallback_series(start: date, n_days: int) -> Weather:
    return {day: fallback_weather(day) for day in _days(start, n_days)}


def load_weather(
    start: date, n_days: int, cache_dir: Path, source: str = "auto"
) -> tuple[Weather, str]:
    """Returns (weather, source_used). source: "auto" (Open-Meteo, else fallback) or
    "fallback"."""
    if source == "fallback":
        return fallback_series(start, n_days), "fallback-climatology"
    end = start + timedelta(days=n_days - 1)
    cache = cache_dir / f"weather_jaipur_{start}_{end}.json"
    try:
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
        else:
            response = httpx.get(
                ARCHIVE_URL,
                params={
                    "latitude": CITY_CENTRE[0],
                    "longitude": CITY_CENTRE[1],
                    "start_date": str(start),
                    "end_date": str(end),
                    "daily": "precipitation_sum,temperature_2m_max",
                    "timezone": "Asia/Kolkata",
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data), encoding="utf-8")
        daily = data["daily"]
        weather: Weather = {}
        for day_text, rain, temp in zip(
            daily["time"], daily["precipitation_sum"], daily["temperature_2m_max"], strict=True
        ):
            day = date.fromisoformat(day_text)
            fallback_rain, fallback_temp = fallback_weather(day)
            # Occasional missing values are filled from the fallback table.
            weather[day] = (
                fallback_rain if rain is None else float(rain),
                fallback_temp if temp is None else float(temp),
            )
        if len(weather) != n_days:
            raise ValueError("incomplete weather series")
        return weather, "open-meteo-archive"
    except (httpx.HTTPError, ValueError, KeyError):
        return fallback_series(start, n_days), "fallback-climatology"
