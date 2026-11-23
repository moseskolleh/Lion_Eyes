"""Neighbourhood names -> coordinates with OpenStreetMap Nominatim.

Only area-type results count (neighbourhood, suburb, village, bay, ...): a
plain search often returns a shop, road or hill that shares the name. Results
are cached and requests are spaced 1 second apart per Nominatim's policy.
"""

from __future__ import annotations

import json
import re
import time

import requests

from floodwatch.config import RAW_DIR
from floodwatch.sources.http import USER_AGENT
from floodwatch.terrain import BOUNDS

URL = "https://nominatim.openstreetmap.org/search"
CACHE = RAW_DIR / "geocode_places.json"
MAP_CACHE = RAW_DIR / "geocode_map_places.json"

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


# --- places for the website map -------------------------------------------
# The analysis above keeps only area-type results. The map can also show a
# flood reported on a street or at a landmark (Kissy Road, King Jimmy Bridge),
# marked as such, so more of the history appears on it. A street or landmark
# counts only if its OpenStreetMap name matches the reported name; among
# same-name streets the most important road wins (Freetown has several Kissy Roads).
ROAD_RANK = ["trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service", "track", "path", "footway"]
LANDMARK_CLASSES = {"amenity", "building", "bridge", "man_made", "tourism", "leisure", "historic", "railway",
                    "waterway", "office", "shop"}
# Spellings in reports -> the spelling OpenStreetMap uses.
ALIASES = {"dwarzack": "Dworzark", "dwazark": "Dworzark", "dwarzark": "Dworzark", "moeba": "Moyiba",
           "moyeiba": "Moyiba", "kuntholoh": "Kuntorloh", "lower kuntolor": "Kuntorloh",
           "colbert": "Colbol", "brooks field": "Brookfields", "portee": "Portee", "kolloh town": "Kolleh Town", "mortomeh": "Mortomeh",
           "cassava town": "Cassava Town", "gray bush": "Gray Bush"}


def map_query(name: str) -> str | None:
    """The searchable part of a reported place name, or None if it is too vague to place."""
    base = re.sub(r"\(.*?\)", "", name).strip(" ,.")
    if "," in base:  # "PWD Junction, Pademba Road" -> the first, most specific part
        base = base.split(",")[0].strip()
    low = base.lower()
    if not base or low in GENERIC or "not named" in name.lower() or low.startswith(("freetown", "sierra leone", "no. ")):
        return None
    if re.match(r"^(behind|near|back of|low-lying|areas? of|parts? of|east part|east and west|downtown|central|eastern|western|lowlands)", low):
        return None
    return ALIASES.get(low, base)


# Streets and landmarks count only inside Freetown and its eastern suburbs, where
# same-name streets elsewhere on the peninsula are the usual mistake.
CITY = (-13.31, 8.38, -13.13, 8.52)  # west, south, east, north


def _in_city(hit: dict) -> bool:
    west, south, east, north = CITY
    return west <= float(hit["lon"]) <= east and south <= float(hit["lat"]) <= north


def _spread_km(hits: list[dict]) -> float:
    pts = [(float(h["lat"]), float(h["lon"])) for h in hits]
    if len(pts) < 2:
        return 0.0
    return max(111.0 * ((a[0] - b[0]) ** 2 + ((a[1] - b[1]) * 0.99) ** 2) ** 0.5 for a in pts for b in pts)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _best_any(query: str, hits: list[dict]) -> dict | None:
    for hit in hits:  # an area first, as in the analysis (plus towns tagged as cities, such as Waterloo)
        if hit.get("type") in PLACE_TYPES | {"city"} and _norm(hit.get("name")) != "freetown" and hit.get("category") in {"place", "natural", "landuse", "boundary"}:
            return {"lat": float(hit["lat"]), "lon": float(hit["lon"]), "osm_type": hit["type"],
                    "display_name": hit.get("display_name"), "precision": "area"}
    q = _norm(query)
    named = [h for h in hits if q and (q == _norm(h.get("name")) or (len(q) > 6 and q in _norm(h.get("name"))))]
    named = [h for h in named if _in_city(h)]
    if _spread_km(named) > 1.5:  # several places share the name: too ambiguous to place
        return None
    streets = [h for h in named if h.get("category") == "highway"]
    if streets:
        hit = min(streets, key=lambda h: ROAD_RANK.index(h["type"]) if h.get("type") in ROAD_RANK else len(ROAD_RANK))
        return {"lat": float(hit["lat"]), "lon": float(hit["lon"]), "osm_type": hit.get("type"),
                "display_name": hit.get("display_name"), "precision": "street"}
    for hit in named:
        if hit.get("category") in LANDMARK_CLASSES:
            return {"lat": float(hit["lat"]), "lon": float(hit["lon"]), "osm_type": hit.get("type"),
                    "display_name": hit.get("display_name"), "precision": "landmark"}
    return None


def lookup_map(names: list[str], known: dict[str, dict] | None = None) -> dict[str, dict | None]:
    """Like ``lookup`` but also accepts streets and landmarks (for the map only).

    ``known`` maps already-placed names to coordinates; a reported name whose
    searchable part is known (``Kissy (Leone Oil facility)`` -> ``Kissy``) reuses them.
    """
    known = known or {}
    cache: dict = json.loads(MAP_CACHE.read_text()) if MAP_CACHE.exists() else {}
    west, south, east, north = BOUNDS
    out = {}
    for name in names:
        query = map_query(name)
        if query is None:
            out[name] = None
            continue
        if query in known:
            out[name] = known[query]
            continue
        if query not in cache:
            try:
                resp = requests.get(URL, params={"q": f"{query}, Sierra Leone", "format": "jsonv2", "limit": 15,
                                                 "countrycodes": "sl", "viewbox": f"{west},{north},{east},{south}",
                                                 "bounded": 1},
                                    headers={"User-Agent": USER_AGENT}, timeout=30)
                resp.raise_for_status()
                keep = ("lat", "lon", "name", "category", "type", "display_name")
                cache[query] = [{k: h.get(k) for k in keep} for h in resp.json()]
            except (requests.RequestException, ValueError):
                print(f"geocode: no answer for {query!r}, skipped")
                continue
            MAP_CACHE.parent.mkdir(parents=True, exist_ok=True)
            MAP_CACHE.write_text(json.dumps(cache, indent=1))
            time.sleep(1.1)  # Nominatim usage policy: at most one request a second
        out[name] = _best_any(query, cache.get(query) or [])
    return out
