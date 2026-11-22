"""Neighbourhood names -> coordinates with OpenStreetMap Nominatim.

Only area-type results count (neighbourhood, suburb, village, bay, ...): a
plain search often returns a shop, road or hill that shares the name. Results
are cached and requests are spaced 1 second apart per Nominatim's policy.
"""

from __future__ import annotations

import json
import time

import requests

from floodwatch.config import RAW_DIR
from floodwatch.sources.http import USER_AGENT
from floodwatch.terrain import BOUNDS

URL = "https://nominatim.openstreetmap.org/search"
CACHE = RAW_DIR / "geocode_places.json"

# Names too general to place on a map.
GENERIC = {"freetown", "central freetown", "western area", "western area urban",
           "western area rural", "east end", "west end", "eastern freetown",
           "western freetown", "central business district"}
PLACE_TYPES = {"neighbourhood", "suburb", "quarter", "village", "hamlet", "town",
               "locality", "isolated_dwelling", "city_block", "bay", "residential"}


def _best(hits: list[dict]) -> dict | None:
    for hit in hits:
        if hit.get("type") in PLACE_TYPES and hit.get("class") in {"place", "natural", "landuse", "boundary"}:
            return {
                "lat": float(hit["lat"]),
                "lon": float(hit["lon"]),
                "osm_type": hit["type"],
                "display_name": hit.get("display_name"),
            }
    return None


def lookup(names: list[str]) -> dict[str, dict | None]:
    cache: dict = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    west, south, east, north = BOUNDS
    for name in names:
        if name in cache or name.strip().lower() in GENERIC:
            continue
        hits = None
        for attempt in range(3):  # Nominatim sometimes answers with an HTML error page
            try:
                resp = requests.get(
                    URL,
                    params={
                        "q": f"{name}, Sierra Leone",
                        "format": "json",
                        "limit": 10,
                        "countrycodes": "sl",
                        "viewbox": f"{west},{north},{east},{south}",
                        "bounded": 1,
                    },
                    headers={"User-Agent": USER_AGENT},
                    timeout=30,
                )
                resp.raise_for_status()
                hits = resp.json()
                break
            except (requests.RequestException, ValueError):
                time.sleep(5 * (attempt + 1))
        if hits is None:  # give up for now; not cached, so retried next run
            print(f"geocode: no answer for {name!r}, skipped")
            continue
        cache[name] = _best(hits)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1))
        time.sleep(1.1)
    return {n: cache.get(n) for n in names}
