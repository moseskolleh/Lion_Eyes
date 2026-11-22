"""ECMWF ensemble rainfall forecasts from the free open-data feed (AWS copy).

The 51-member ensemble (ENS, 0.25 deg) runs at 00 and 12 UTC. Total
precipitation ``tp`` is accumulated from the start of the run, so the rain on
forecast day k is tp(24k) - tp(24(k-1)). Each member's global field is about
400 KB; we fetch only those fields by byte range using the published index
and keep the four grid points over the peninsula.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

from floodwatch.config import DATA_DIR
from floodwatch.sources.http import USER_AGENT

BUCKET = "https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com"
# 0.25 deg grid points covering the peninsula (city, east, south, Waterloo).
POINTS = ((8.5, -13.25), (8.5, -13.0), (8.25, -13.25), (8.25, -13.0))
STEPS = (24, 48, 72)
# Kept in the repository (small: ~20 KB per run) to calibrate thresholds later.
CACHE = DATA_DIR / "archive" / "ecmwf"


def _base(run_day: date, hour: int, step: int) -> str:
    return f"{BUCKET}/{run_day:%Y%m%d}/{hour:02d}z/ifs/0p25/enfo/{run_day:%Y%m%d}{hour:02d}0000-{step}h-enfo-ef"


def latest_run(now: datetime | None = None) -> tuple[date, int]:
    """Most recent 00/12 UTC run whose day-3 file is published."""
    now = now or datetime.now(timezone.utc)
    s = requests.Session()
    for back in range(0, 4 * 12, 12):
        t = now - timedelta(hours=back)
        hour = 12 if t.hour >= 12 else 0
        r = s.head(_base(t.date(), hour, STEPS[-1]) + ".index", timeout=30)
        if r.status_code == 200:
            return t.date(), hour
    raise RuntimeError("No recent ECMWF ensemble run found")


def _decode_points(message: bytes) -> np.ndarray:
    import eccodes

    gid = eccodes.codes_new_from_message(message)
    try:
        ni = eccodes.codes_get(gid, "Ni")
        lat0 = eccodes.codes_get(gid, "latitudeOfFirstGridPointInDegrees")
        lon0 = eccodes.codes_get(gid, "longitudeOfFirstGridPointInDegrees")
        dlat = eccodes.codes_get(gid, "jDirectionIncrementInDegrees")
        dlon = eccodes.codes_get(gid, "iDirectionIncrementInDegrees")
        values = eccodes.codes_get_values(gid)
    finally:
        eccodes.codes_release(gid)
    out = []
    for lat, lon in POINTS:
        j = int(round((lat0 - lat) / dlat))
        i = int(round(((lon - lon0) % 360) / dlon))
        out.append(values[j * ni + i] * 1000.0)  # metres -> mm
    return np.array(out)


_local = threading.local()


def _get(url: str, headers: dict | None = None, tries: int = 10) -> requests.Response:
    """GET with back-off: the archive answers 503 "SlowDown" when busy."""
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
        _local.session.headers["User-Agent"] = USER_AGENT
    for attempt in range(tries):
        try:
            r = _local.session.get(url, headers=headers, timeout=120)
            if r.status_code in (200, 206):
                return r
            if r.status_code in (403, 404):
                r.raise_for_status()  # not there: no point retrying
        except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError, requests.Timeout):
            if attempt == tries - 1:  # dropped or cut-off transfers are worth retrying
                raise
        time.sleep(min(120, 2 * 2**attempt))
    raise RuntimeError(f"ECMWF open data did not answer: {url}")


def fetch_run(run_day: date, hour: int, workers: int = 8) -> pd.DataFrame:
    """Accumulated tp (mm) at each peninsula point for every member and step."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{run_day:%Y%m%d}{hour:02d}.csv"
    if path.exists():
        return pd.read_csv(path)
    jobs = []
    for step in STEPS:
        base = _base(run_day, hour, step)
        index = [json.loads(line) for line in _get(base + ".index").text.splitlines() if line.strip()]
        jobs += [(base, step, e) for e in index if e.get("param") == "tp"]

    def one(job: tuple) -> list[tuple]:
        base, step, entry = job
        start, length = entry["_offset"], entry["_length"]
        msg = _get(base + ".grib2", headers={"Range": f"bytes={start}-{start + length - 1}"}).content
        member = 0 if entry["type"] == "cf" else int(entry["number"])
        return [(member, step, lat, lon, round(float(tp), 2)) for (lat, lon), tp in zip(POINTS, _decode_points(msg))]

    with ThreadPoolExecutor(workers) as pool:
        rows = [row for rows in pool.map(one, jobs) for row in rows]
    df = pd.DataFrame(rows, columns=["member", "step_h", "lat", "lon", "tp_mm"])
    df = df.sort_values(["step_h", "member", "lat", "lon"], ascending=[True, True, False, True])
    df.to_csv(path, index=False)
    return df


def daily_rain(run: pd.DataFrame) -> pd.DataFrame:
    """Rain per forecast day (1-3), per member: peninsula mean and max point."""
    wide = run.pivot_table(index=["member", "lat", "lon"], columns="step_h", values="tp_mm")
    days = pd.DataFrame(index=wide.index)
    prev = 0.0
    for k, step in enumerate(STEPS, 1):
        days[k] = (wide[step] - prev).clip(lower=0)
        prev = wide[step]
    days.columns.name = "day"
    long = days.stack().rename("mm").reset_index()
    g = long.groupby(["member", "day"])["mm"]
    return pd.DataFrame({"mean_mm": g.mean(), "max_mm": g.max()}).reset_index()
