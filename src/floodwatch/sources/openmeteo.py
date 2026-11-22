"""Hourly rainfall and sea level from Open-Meteo (no account needed).

Rainfall comes from ECMWF reanalysis and archived forecasts:
  * ``era5``      0.25 deg (~28 km), 1940 onward
  * ``ecmwf_ifs`` ~9 km archived operational analyses, 2017 onward
Sea level (tide plus surge, metres relative to mean sea level) comes from the
Open-Meteo marine API.

Both are model products, not measurements: they are expected to under-state
short, intense tropical downpours. The hindcast measures how much that matters.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd

from floodwatch.config import RAW_DIR, Point
from floodwatch.sources.http import cached_get_json

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

MODEL_FIRST_YEAR = {"era5": 1940, "ecmwf_ifs": 2017}


def _year_ranges(first_year: int, end: date) -> Iterable[tuple[str, str]]:
    for year in range(first_year, end.year + 1):
        start = date(year, 1, 1)
        stop = min(date(year, 12, 31), end)
        if start <= stop:
            yield start.isoformat(), stop.isoformat()


def fetch_rain(
    model: str, points: Iterable[Point], first_year: int, end: date
) -> pd.DataFrame:
    """Hourly precipitation (mm) for each point, one request per year."""
    points = list(points)
    first_year = max(first_year, MODEL_FIRST_YEAR[model])
    frames: list[pd.DataFrame] = []
    for start, stop in _year_ranges(first_year, end):
        body = cached_get_json(
            ARCHIVE_URL,
            {
                "latitude": ",".join(f"{p.lat:.3f}" for p in points),
                "longitude": ",".join(f"{p.lon:.3f}" for p in points),
                "start_date": start,
                "end_date": stop,
                "hourly": "precipitation",
                "timezone": "UTC",
                "models": model,
            },
            RAW_DIR / "openmeteo" / "rain" / model,
        )
        bodies = body if isinstance(body, list) else [body]
        for point, loc in zip(points, bodies):
            hourly = loc["hourly"]
            frames.append(
                pd.DataFrame(
                    {
                        "time": pd.to_datetime(hourly["time"]),
                        "point": point.key,
                        "grid_lat": loc["latitude"],
                        "grid_lon": loc["longitude"],
                        "precip_mm": hourly["precipitation"],
                    }
                )
            )
    df = pd.concat(frames, ignore_index=True)
    df["model"] = model
    return df


def fetch_sea_level(point: Point, first_year: int, end: date) -> pd.DataFrame:
    """Hourly modelled sea level (m above mean sea level) at ``point``."""
    frames: list[pd.DataFrame] = []
    for start, stop in _year_ranges(first_year, end):
        body = cached_get_json(
            MARINE_URL,
            {
                "latitude": f"{point.lat:.3f}",
                "longitude": f"{point.lon:.3f}",
                "start_date": start,
                "end_date": stop,
                "hourly": "sea_level_height_msl",
                "timezone": "UTC",
            },
            RAW_DIR / "openmeteo" / "sea_level",
        )
        hourly = body["hourly"]
        frames.append(
            pd.DataFrame(
                {
                    "time": pd.to_datetime(hourly["time"]),
                    "sea_level_m": hourly["sea_level_height_msl"],
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
