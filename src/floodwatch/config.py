"""Shared settings: where we look, which seasons, where files live.

Sierra Leone is on UTC all year (no daylight saving), so every timestamp in
this project is UTC and equals local clock time in Freetown.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
EVENTS_DIR = DATA_DIR / "events"
DERIVED_DIR = DATA_DIR / "derived"


@dataclass(frozen=True)
class Point:
    key: str
    name: str
    lat: float
    lon: float


# Sample points spread across the Freetown peninsula. Global reanalysis grids
# are 9-25 km wide, so these mostly land in 2-4 distinct grid cells; we keep
# several so that the analysis can use the wettest cell rather than one guess.
POINTS: tuple[Point, ...] = (
    Point("central", "Central Freetown / Kroo Bay", 8.484, -13.234),
    Point("east", "Kissy / Wellington", 8.455, -13.165),
    Point("hills", "Regent / Sugar Loaf hills", 8.430, -13.215),
    Point("west", "Lumley / Goderich", 8.430, -13.285),
    Point("waterloo", "Waterloo (Western Rural)", 8.340, -13.070),
)

# Sea level is read just offshore of central Freetown.
SEA_POINT = Point("sea", "Freetown harbour approach", 8.500, -13.250)

# The analysis window. Flood reports before 2000 are too sparse to be useful.
FIRST_YEAR = 2000

# Rainy season used for scoring warnings (inclusive months). Floods outside it
# are kept in the catalogue but are rare.
SEASON_MONTHS = (5, 6, 7, 8, 9, 10, 11)
