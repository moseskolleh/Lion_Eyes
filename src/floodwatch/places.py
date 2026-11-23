"""Past flood places for the website map.

Every place named in the flood history, with coordinates where OpenStreetMap
can place it: neighbourhoods first (as in the terrain analysis), then streets
and landmarks, each marked with its precision. Written to
``data/derived/map_places.csv`` (committed) so the daily site build never
calls the geocoder. Refresh after a new research round with
``floodwatch places``.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from floodwatch import config, events, geocode

MAP_PLACES_CSV = config.DERIVED_DIR / "map_places.csv"
COLUMNS = ["place", "events", "lat", "lon", "precision", "osm_type", "osm_name"]


def _from_analysis() -> dict[str, dict]:
    """Area-type coordinates already found by the terrain analysis."""
    path = config.DERIVED_DIR / "flood_places.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    df = df[df["geocoded"].astype(bool)]
    return {r["place"]: {"lat": r["lat"], "lon": r["lon"], "osm_type": r["osm_type"], "precision": "area",
                         "display_name": None} for _, r in df.iterrows()}


def build(online: bool = True) -> pd.DataFrame:
    cat = events.load_catalogue()
    counts = Counter(n.strip() for locs in cat["locations"] for n in locs if n.strip())
    known = _from_analysis()
    todo = sorted(n for n in counts if n not in known)
    found = geocode.lookup_map(todo, known) if online else {}
    rows = []
    for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        hit = known.get(name) or found.get(name)
        rows.append({"place": name, "events": n,
                     "lat": round(hit["lat"], 5) if hit else None, "lon": round(hit["lon"], 5) if hit else None,
                     "precision": hit["precision"] if hit else None, "osm_type": hit.get("osm_type") if hit else None,
                     "osm_name": (hit.get("display_name") or "").split(",")[0] if hit else None})
    df = pd.DataFrame(rows, columns=COLUMNS)
    df.to_csv(MAP_PLACES_CSV, index=False)
    return df


def load() -> pd.DataFrame:
    """Placed rows only; falls back to the analysis file if the map file is missing."""
    if MAP_PLACES_CSV.exists():
        df = pd.read_csv(MAP_PLACES_CSV)
    else:
        df = pd.DataFrame([{"place": k, **v} for k, v in _from_analysis().items()])
    return df.dropna(subset=["lat", "lon"]) if len(df) else df
