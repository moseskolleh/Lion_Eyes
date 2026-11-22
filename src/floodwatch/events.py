"""The flood history: every past Freetown flood we can source.

Research produces JSON Lines files (one event per line). ``build_catalogue``
validates and merges them into ``data/events/freetown_floods.csv``, the single
file the rest of the project reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from floodwatch.config import EVENTS_DIR

CATALOGUE_CSV = EVENTS_DIR / "freetown_floods.csv"

FIELDS = [
    "date",
    "date_confidence",
    "time_of_day",
    "end_date",
    "type",
    "locations",
    "deaths",
    "affected",
    "houses_damaged",
    "rain_note",
    "summary",
    "evidence",
    "sources",
]
LIST_SEP = " | "
DATE_CONFIDENCE = {"exact", "approx_day", "month_only"}
TYPES = {"flash_flood", "coastal_flood", "landslide", "mixed"}

# Low-lying shoreline and estuary communities, where high tide can stop
# streams draining. Matched case-insensitively as substrings.
COASTAL_PLACES = (
    "kroo bay", "susan's bay", "susans bay", "moa wharf", "colbol", "kanikay",
    "mabella", "marbella", "cockle bay", "portee", "rokupa", "thompson bay",
    "kolleh town", "old wharf", "destruction bay", "crab town", "magazine",
    "kissy dock", "culvert", "aberdeen", "lumley beach", "big wharf",
    "government wharf", "dworzark wharf", "fisher lane", "sorie town wharf",
)


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{n}: bad JSON: {exc}") from exc
    return rows


def _validate(row: dict, where: str) -> dict:
    missing = [f for f in FIELDS if f not in row]
    if missing:
        raise ValueError(f"{where}: missing {missing}")
    pd.Timestamp(row["date"])  # raises if not a date
    if row["date_confidence"] not in DATE_CONFIDENCE:
        raise ValueError(f"{where}: date_confidence {row['date_confidence']!r}")
    if row["type"] not in TYPES:
        raise ValueError(f"{where}: type {row['type']!r}")
    if not row["sources"]:
        raise ValueError(f"{where}: no sources")
    return row


def _merge_same_day(group: pd.DataFrame) -> pd.Series:
    """Combine duplicate records of one storm day from different files."""
    first = group.iloc[0].copy()
    for col in ("locations", "sources"):
        seen: list[str] = []
        for items in group[col]:
            for item in items:
                if item not in seen:
                    seen.append(item)
        first[col] = seen
    for col in ("deaths", "affected", "houses_damaged"):
        first[col] = group[col].max()
    return first


def is_coastal(locations: list[str]) -> bool:
    text = " ".join(locations).lower()
    return any(place in text for place in COASTAL_PLACES)


def build_catalogue(inputs: list[str]) -> pd.DataFrame:
    rows = []
    for name in inputs:
        path = Path(name)
        for i, row in enumerate(_read_jsonl(path), 1):
            rows.append(_validate(row, f"{path.name}#{i}"))
    df = pd.DataFrame(rows)[FIELDS]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = (
        df.groupby("date", sort=True, group_keys=False)
        .apply(_merge_same_day, include_groups=False)
        .reset_index()
    )
    df.insert(0, "event_id", [f"FT-{d:%Y%m%d}" for d in df["date"]])
    df["coastal"] = df["locations"].map(is_coastal)
    out = df.copy()
    for col in ("locations", "sources"):
        out[col] = out[col].map(LIST_SEP.join)
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(CATALOGUE_CSV, index=False)
    return df


def load_catalogue(path: Path = CATALOGUE_CSV) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    for col in ("locations", "sources"):
        df[col] = df[col].fillna("").map(lambda s: [x for x in s.split(LIST_SEP) if x])
    return df
