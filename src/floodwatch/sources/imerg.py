"""Half-hourly satellite rainfall from NASA IMERG V07 (0.1 deg, 2000 onward).

IMERG blends passive-microwave satellite overpasses with infrared imagery into
a rain rate every 30 minutes. We read the Final run (gauge-corrected monthly,
~3.5 months behind real time) and fall back to the Late run (~14 hours behind)
for recent days. Only the 12 cells over the Freetown peninsula are read, via
OPeNDAP subsetting from NASA GES DISC.

Access needs a NASA Earthdata Login token sent as a bearer token. In this
project's cloud environment the network proxy adds it; elsewhere set
``EARTHDATA_TOKEN``.
"""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd
import requests

from floodwatch.config import RAW_DIR
from floodwatch.sources.http import USER_AGENT

HOST = "https://gpm1.gesdisc.eosdis.nasa.gov"
PRODUCTS = ("GPM_3IMERGHH.07", "GPM_3IMERGHHL.07")  # Final, then Late
# Grid indices on the global 0.1 deg grid: lat 8.25-8.55 N, lon 13.25-13.05 W.
LAT_I = (982, 985)
LON_I = (1667, 1669)
CACHE = RAW_DIR / "imerg"
FILL = -9999.9


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    token = os.environ.get("EARTHDATA_TOKEN")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


def _get(s: requests.Session, url: str, tries: int = 5) -> requests.Response:
    wait = 5.0
    for _ in range(tries):
        try:
            r = s.get(url, timeout=90)
        except requests.RequestException:
            r = None
        if r is not None and r.status_code == 200:
            return r
        if r is not None and r.status_code in (401, 403, 404):
            r.raise_for_status()
        time.sleep(wait)
        wait *= 2
    raise RuntimeError(f"GET failed after {tries} tries: {url}")


def _day_files(s: requests.Session, day: date) -> tuple[str, list[str]]:
    doy = day.timetuple().tm_yday
    for product in PRODUCTS:
        url = f"{HOST}/data/GPM_L3/{product}/{day.year}/{doy:03d}/"
        try:
            html = _get(s, url).text
        except requests.HTTPError:
            continue
        names = sorted(set(re.findall(r"3B-HHR[^\"<>]*?\.HDF5(?=[\"<])", html)))
        if len(names) == 48:
            return product, names
    raise RuntimeError(f"No complete IMERG day for {day}")


def _read_half_hour(s: requests.Session, product: str, day: date, name: str) -> pd.DataFrame:
    doy = day.timetuple().tm_yday
    sub = f"precipitation%5B0:0%5D%5B{LON_I[0]}:{LON_I[1]}%5D%5B{LAT_I[0]}:{LAT_I[1]}%5D"
    url = f"{HOST}/opendap/GPM_L3/{product}/{day.year}/{doy:03d}/{name}.ascii?{sub}"
    text = _get(s, url).text
    start = re.search(r"\.(\d{8})-S(\d{6})-", name)
    t0 = pd.Timestamp(f"{start.group(1)}T{start.group(2)}")
    rows = []
    for line in text.splitlines():
        m = re.match(r"precipitation\[0\]\[(\d+)\],(.*)", line.replace(" ", ""))
        if not m:
            continue
        lon = -180 + (LON_I[0] + int(m.group(1))) * 0.1 + 0.05
        for j, v in enumerate(m.group(2).split(",")):
            lat = -90 + (LAT_I[0] + j) * 0.1 + 0.05
            rate = float(v)
            rows.append((t0, round(lat, 2), round(lon, 2), None if rate <= FILL + 1 else rate))
    return pd.DataFrame(rows, columns=["time", "lat", "lon", "rate_mm_h"])


def fetch_day(day: date, workers: int = 4) -> pd.DataFrame:
    """All 48 half-hours for ``day`` (UTC) over the peninsula, cached."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{day.isoformat()}.csv.gz"
    if path.exists():
        return pd.read_csv(path, parse_dates=["time"])
    s = _session()
    product, names = _day_files(s, day)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        frames = list(pool.map(lambda n: _read_half_hour(s, product, day, n), names))
    df = pd.concat(frames, ignore_index=True)
    df["product"] = "final" if product == PRODUCTS[0] else "late"
    df.to_csv(path, index=False)
    return df


DAILY_PRODUCTS = ("GPM_3IMERGDL.07", "GPM_3IMERGDE.07")  # Late (~14 h), then Early (~4 h)


def daily_total(day: date) -> dict:
    """Near-real-time daily rain (mm) over the peninsula cells: mean and max."""
    s = _session()
    for product in DAILY_PRODUCTS:
        folder = f"{HOST}/data/GPM_L3/{product}/{day.year}/{day.month:02d}/"
        try:
            html = _get(s, folder).text
        except (requests.HTTPError, RuntimeError):
            continue
        names = sorted(set(re.findall(rf"3B-DAY-[LE]\.MS\.MRG\.3IMERG\.{day:%Y%m%d}[^\"<>]*?\.nc4(?=[\"<])", html)))
        if not names:
            continue
        lat_hi = LAT_I[0] + 2  # the 8.55 N row is mostly water
        sub = f"precipitation%5B0:0%5D%5B{LON_I[0]}:{LON_I[1]}%5D%5B{LAT_I[0]}:{lat_hi}%5D"
        text = _get(s, f"{HOST}/opendap/GPM_L3/{product}/{day.year}/{day.month:02d}/{names[-1]}.ascii?{sub}").text
        # Rows look like "precipitation[0][1], v, v, v" (HDF5 grids) or
        # "precipitation.precipitation[...lon=-13.25], v, v, v" (netCDF grids).
        values = [
            float(v)
            for line in text.splitlines()
            if re.match(r"precipitation(\.precipitation)?\[", line.replace(" ", ""))
            for v in line.split(",")[1:]
            if float(v) > FILL + 1
        ]
        if values:
            return {"date": day.isoformat(), "product": product, "mean_mm": round(float(np.mean(values)), 1),
                    "max_mm": round(float(np.max(values)), 1)}
    raise RuntimeError(f"No IMERG daily total for {day}")


HH_NEAR_REAL_TIME = ("GPM_3IMERGHH.07", "GPM_3IMERGHHL.07", "GPM_3IMERGHHE.07")  # Final, Late, Early (~4 h)


def total_until(day: date, until_hour: int = 12, workers: int = 4) -> dict:
    """Rain over the peninsula on ``day`` from 00:00 to ``until_hour`` UTC (mm).

    Used by the evening Outlook for "rain so far today". Takes the most refined
    half-hourly run that already covers those hours: Final, then Late, then
    Early. Same cells as `daily_total` (the 8.55 N row is mostly water).
    """
    cached = CACHE / f"until_{day.isoformat()}_{until_hour:02d}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    s = _session()
    doy = day.timetuple().tm_yday
    for product in HH_NEAR_REAL_TIME:
        try:
            html = _get(s, f"{HOST}/data/GPM_L3/{product}/{day.year}/{doy:03d}/").text
        except (requests.HTTPError, RuntimeError):
            continue
        names = sorted(n for n in set(re.findall(r"3B-HHR[^\"<>]*?\.HDF5(?=[\"<])", html))
                       if int(re.search(r"-S(\d{2})\d{4}-", n).group(1)) < until_hour)
        if len(names) < 2 * until_hour:
            continue
        with ThreadPoolExecutor(max_workers=workers) as pool:
            df = pd.concat(pool.map(lambda n: _read_half_hour(s, product, day, n), names), ignore_index=True)
        df = df[df["lat"] <= 8.45]
        per_cell = df.groupby(["lat", "lon"])["rate_mm_h"].sum(min_count=1).dropna() * 0.5  # mm/h x 0.5 h
        if len(per_cell):
            out = {"date": day.isoformat(), "until": f"{until_hour:02d}:00 UTC", "product": product,
                   "mean_mm": round(float(per_cell.mean()), 1), "max_mm": round(float(per_cell.max()), 1)}
            if product == HH_NEAR_REAL_TIME[0]:  # Final run: will not change, so keep it
                CACHE.mkdir(parents=True, exist_ok=True)
                cached.write_text(json.dumps(out))
            return out
    raise RuntimeError(f"No IMERG half-hourly rain covering {day} 00-{until_hour:02d} UTC yet")


def fetch_days(days: list[date], workers: int = 4) -> pd.DataFrame:
    return pd.concat([fetch_day(d, workers) for d in sorted(set(days))], ignore_index=True)
