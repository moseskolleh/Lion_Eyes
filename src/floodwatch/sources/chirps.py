"""Daily rainfall from CHIRPS v3 (satellite + rain gauges, 0.05 deg grid).

We use the ``sat`` daily product: each 5-day (pentad) total is built from
satellite estimates blended with station observations, then split across days
using NASA IMERG satellite rainfall. Daily values are therefore good for "how
wet was this day" but carry no sub-daily timing.

The files are global GeoTIFFs; we read only the Freetown peninsula window over
HTTP byte ranges and cache the cell values per year.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import pandas as pd

from floodwatch.config import RAW_DIR

BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat"
# Peninsula bounding box (west, south, east, north), whole cells.
BOUNDS = (-13.32, 8.20, -12.98, 8.56)
CACHE = RAW_DIR / "chirps" / "sat"


def _url(day: date) -> str:
    return f"{BASE}/{day.year}/chirps-v3.0.sat.{day:%Y.%m.%d}.tif"


def _read_window(day: date) -> pd.DataFrame | None:
    import rasterio
    from rasterio.windows import from_bounds

    env = dict(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_MULTIRANGE="YES",
        GDAL_HTTP_MAX_RETRY="4",
        GDAL_HTTP_RETRY_DELAY="5",
        GDAL_HTTP_TIMEOUT="60",
        GDAL_HTTP_CONNECTTIMEOUT="20",
    )
    try:
        with rasterio.Env(**env), rasterio.open(f"/vsicurl/{_url(day)}") as ds:
            window = from_bounds(*BOUNDS, ds.transform).round_offsets().round_lengths()
            values = ds.read(1, window=window)
            transform = ds.window_transform(window)
    except Exception:  # missing day or network failure; reported by caller
        return None
    rows, cols = np.indices(values.shape)
    lon = transform.c + (cols + 0.5) * transform.a
    lat = transform.f + (rows + 0.5) * transform.e
    return pd.DataFrame(
        {
            "date": pd.Timestamp(day),
            "lat": lat.ravel().round(3),
            "lon": lon.ravel().round(3),
            "precip_mm": values.ravel().astype(float),
        }
    )


def _read_politely(day: date, pause: float, waits: tuple[int, ...] = (30, 90, 240, 600)) -> pd.DataFrame | None:
    """Read one day; on failure (usually HTTP 429) wait and retry."""
    for wait in (0, *waits):
        if wait:
            time.sleep(wait)
        frame = _read_window(day)
        if frame is not None:
            time.sleep(pause)
            return frame
    return None


def fetch_year(
    year: int, months: tuple[int, int] = (4, 11), workers: int = 2, pause: float = 0.5
) -> pd.DataFrame:
    """All cells for every day in ``months`` (inclusive) of ``year``.

    The CHC server rate-limits (HTTP 429; six parallel streams tripped it), so
    we use two paced streams with long back-off on failure.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{year}.csv.gz"
    if path.exists():
        return pd.read_csv(path, parse_dates=["date"])
    first = date(year, months[0], 1)
    last = min(date(year, months[1] + 1, 1) - timedelta(days=1), date.today() - timedelta(days=45))
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        frames = list(pool.map(lambda d: _read_politely(d, pause), days))
    missing = [d for d, f in zip(days, frames) if f is None]
    if missing:
        print(f"CHIRPS {year}: {len(missing)} days missing, e.g. {missing[:3]}")
    df = pd.concat([f for f in frames if f is not None], ignore_index=True)
    if len(missing) == 0:  # only cache complete years
        df.to_csv(path, index=False)
    return df


def fetch(first_year: int, last_year: int) -> pd.DataFrame:
    return pd.concat([fetch_year(y) for y in range(first_year, last_year + 1)], ignore_index=True)


def daily_features(cells: pd.DataFrame) -> pd.DataFrame:
    """Per day: wettest-cell total, peninsula mean, and rain in prior days."""
    # Drop cells that are sea (CHIRPS is land-only; sea is stored as negative).
    cells = cells[cells["precip_mm"] >= 0]
    g = cells.groupby("date")["precip_mm"]
    daily = pd.DataFrame({"day_max": g.max(), "day_mean": g.mean()})
    full = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full)
    daily["prev_3d"] = daily["day_mean"].shift(1).rolling(3, min_periods=3).sum()
    daily["prev_7d"] = daily["day_mean"].shift(1).rolling(7, min_periods=7).sum()
    daily["day_plus_prev_3d"] = daily["day_mean"] + daily["prev_3d"]
    daily.index.name = "date"
    return daily
