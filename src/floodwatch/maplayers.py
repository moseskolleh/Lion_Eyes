"""Map layers for the website: ``floodwatch layers`` -> ``site_assets/layers/``.

Raster overlays on the 1-arcsecond (~30 m) elevation grid, as transparent PNGs
(one image each, placed by the bounds in ``layers.json``):

* ``hillshade.png``  - the shape of the hills (the "mountains" Lion Eyes watches)
* ``lowground.png``  - low ground near streams or the shore (height above the
  nearest stream < 3 m and elevation < 20 m): where flood water gathers
* ``steep.png``      - slopes steeper than 25 degrees: where landslides and
  wall collapses are likelier
* ``population.png`` - people per hectare, estimated from building footprints:
  each building counts as the peninsula average (Meta HRSL total / buildings,
  ~3.6 people), smoothed over ~90 m. HRSL itself spreads each census area's
  total evenly over its buildings, which draws hard edges at census boundaries.

Vectors (GeoJSON):

* ``streams.geojson``    - the stream network (catchment >= 0.5 km2)
* ``roads.geojson``      - main roads (Overture); ``low_roads`` marks the
  stretches that run over low ground and may flood
* ``facilities.geojson`` - hospitals and clinics, schools, police stations and
  places of worship (often used as shelters), from Overture places, flagged
  when on low ground or steep slopes

Tiles: ``buildings/{z}/{x}/{y}.png`` (zoom 13-16): every building footprint
(Overture), coloured by the ground it stands on. Only tiles with buildings
are written; ``layers.json`` lists them so the map does not ask for the rest.

Inputs are static, so this runs once and the outputs are committed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from floodwatch import config, population, terrain, zones

OUT = config.REPO_ROOT / "site_assets" / "layers"
OVERTURE = f"overturemaps-us-west-2/release/{population.OVERTURE_RELEASE}"
CACHE = config.RAW_DIR / "overture"

# Colours (the site's map palette): low ground blue, steep orange, neutral grey.
LOW_RGB = (42, 120, 214)
STEEP_RGB = (235, 104, 52)
NEUTRAL_RGB = (150, 156, 164)
# Sequential (one hue, light -> dark) for people per hectare.
# Steps follow the data: median ~50 people/ha, the densest 3% over ~250.
POP_STEPS = [(5, "#f3e8ff"), (25, "#d8b4fe"), (60, "#a855f7"), (120, "#7e22ce"), (200, "#4c1d95")]

BUILDING_ZOOMS = range(13, 17)
ROAD_CLASSES = ("motorway", "trunk", "primary", "secondary", "tertiary")
FACILITY_GROUPS = {  # Overture basic_category (as found in Freetown) -> group shown on the map
    "health": ("hospital", "health_care", "specialized_health_care", "pediatric_clinic",
               "emergency_or_urgent_care_facility"),
    "school": ("college_university", "education", "high_school", "elementary_school", "middle_school",
               "preschool", "specialty_school"),
    "emergency": ("police_station", "fire_station"),
    "worship": ("christian_place_of_worship", "muslim_place_of_worship"),  # often used as shelters
}


# --- grid helpers ------------------------------------------------------------

def _bounds(h: terrain.Hydrology) -> list[list[float]]:
    """[[south, west], [north, east]] of the elevation grid (Leaflet order)."""
    t, (rows, cols) = h.transform, h.dem.shape
    west, north = t.c, t.f
    east, south = west + t.a * cols, north + t.e * rows
    return [[round(south, 6), round(west, 6)], [round(north, 6), round(east, 6)]]


def _masks(h: terrain.Hydrology) -> tuple[np.ndarray, np.ndarray]:
    land = h.land
    low = land & (np.nan_to_num(h.hand, nan=99) < zones.LOW_HAND_M) & (h.dem < zones.LOW_ELEV_M)
    steep = land & (np.nan_to_num(h.slope_deg(), nan=0) > zones.STEEP_DEG)
    return low, steep


def _cells(h: terrain.Hydrology, lon: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Grid row/col for each point, and whether it falls inside the grid."""
    t = h.transform
    col = np.floor((lon - t.c) / t.a).astype(int)
    row = np.floor((lat - t.f) / t.e).astype(int)
    ok = (row >= 0) & (row < h.dem.shape[0]) & (col >= 0) & (col < h.dem.shape[1])
    return np.clip(row, 0, h.dem.shape[0] - 1), np.clip(col, 0, h.dem.shape[1] - 1), ok


def _png(rgba: np.ndarray, path: Path) -> None:
    from PIL import Image

    Image.fromarray(rgba.astype(np.uint8), "RGBA").save(path, optimize=True)


# --- raster overlays ---------------------------------------------------------

def hillshade(h: terrain.Hydrology, azimuth: float = 315, altitude: float = 45) -> np.ndarray:
    """Shadows (black) and lit slopes (white) as semi-transparent RGBA, so the
    relief shows on both the light and the dark map."""
    lat = (terrain.BOUNDS[1] + terrain.BOUNDS[3]) / 2
    dx = abs(h.transform.a) * 111_320 * np.cos(np.radians(lat))
    dy = abs(h.transform.e) * 110_570
    z = np.where(h.land, h.dem, np.nan).astype(float)
    z = np.where(np.isnan(z), np.nanmin(z), z)
    d_row, d_col = np.gradient(z, dy, dx)
    dz_east, dz_north = d_col, -d_row  # rows run southwards
    norm = np.sqrt(dz_east**2 + dz_north**2 + 1)
    az, alt = np.radians(azimuth), np.radians(altitude)
    light = np.array([np.cos(alt) * np.sin(az), np.cos(alt) * np.cos(az), np.sin(alt)])
    shade = (-dz_east * light[0] - dz_north * light[1] + light[2]) / norm
    dev = shade - np.sin(alt)  # 0 on flat ground
    rgba = np.zeros(h.dem.shape + (4,))
    dark = dev < 0
    rgba[..., :3] = np.where(dark[..., None], 0, 255)
    rgba[..., 3] = np.where(dark, np.clip(-dev * 330, 0, 150), np.clip(dev * 220, 0, 90))
    rgba[~h.land, 3] = 0
    return rgba


def _mask_rgba(mask: np.ndarray, rgb: tuple[int, int, int], alpha: int) -> np.ndarray:
    rgba = np.zeros(mask.shape + (4,))
    rgba[mask, :3] = rgb
    rgba[mask, 3] = alpha
    return rgba


def population_rgba(h: terrain.Hydrology) -> np.ndarray:
    from scipy.ndimage import uniform_filter

    b = population.buildings()
    rr, cc, ok = _cells(h, b["lon"].to_numpy(), b["lat"].to_numpy())
    count = np.zeros(h.dem.shape)
    np.add.at(count, (rr[ok], cc[ok]), 1)
    per_building = population.population(h).sum() / ok.sum()
    per_ha = uniform_filter(count, size=3) * per_building / (h.cell_km2 * 100)
    rgba = np.zeros(h.dem.shape + (4,))
    for lo, colour in POP_STEPS:
        sel = per_ha >= lo
        rgb = tuple(int(colour[i : i + 2], 16) for i in (1, 3, 5))
        rgba[sel, :3] = rgb
        rgba[sel, 3] = 200
    return rgba


# --- vectors -----------------------------------------------------------------

def streams(h: terrain.Hydrology, min_km2: float = 0.5) -> dict:
    """Stream lines traced cell to cell down the flow directions."""
    rows, cols = h.dem.shape
    on = h.land & (h.upstream_km2 >= min_km2)
    offsets = terrain.D8_OFFSETS
    down = {}
    for r, c in zip(*np.nonzero(on)):
        dr, dc = offsets.get(int(h.fdir[r, c]), (0, 0))
        rr, cc = r + dr, c + dc
        down[(r, c)] = (rr, cc) if 0 <= rr < rows and 0 <= cc < cols else None
    n_up: dict = {}
    for cell, nxt in down.items():
        if nxt is not None and nxt in down:
            n_up[nxt] = n_up.get(nxt, 0) + 1
    t = h.transform

    def xy(cell):
        r, c = cell
        return [round(t.c + (c + 0.5) * t.a, 5), round(t.f + (r + 0.5) * t.e, 5)]

    feats = []
    starts = [cell for cell in down if n_up.get(cell, 0) != 1]  # heads and junctions
    for start in starts:
        line, cell = [xy(start)], start
        while True:
            nxt = down.get(cell)
            if nxt is None:
                break
            line.append(xy(nxt))
            if nxt not in down or n_up.get(nxt, 0) != 1:
                break
            cell = nxt
        if len(line) >= 2:
            km2 = float(h.upstream_km2[cell])
            feats.append({"type": "Feature", "properties": {"km2": round(km2, 1)},
                          "geometry": {"type": "LineString", "coordinates": line}})
    return {"type": "FeatureCollection", "features": feats}


def _overture(name: str, theme: str, columns: list[str], extra=None) -> pd.DataFrame:
    """Rows of an Overture theme inside the peninsula bounds, cached as parquet."""
    path = CACHE / f"{name}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    import pyarrow.dataset as ds
    import pyarrow.fs as pafs

    west, south, east, north = terrain.BOUNDS
    data = ds.dataset(f"{OVERTURE}/{theme}/", filesystem=pafs.S3FileSystem(anonymous=True, region="us-west-2"),
                      format="parquet")
    xmin, ymin = ds.field("bbox", "xmin"), ds.field("bbox", "ymin")
    xmax, ymax = ds.field("bbox", "xmax"), ds.field("bbox", "ymax")
    where = (xmax >= west) & (xmin <= east) & (ymax >= south) & (ymin <= north)
    if extra is not None:
        where = where & extra(ds)
    df = data.to_table(columns=columns, filter=where).to_pandas()
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return df


def roads(h: terrain.Hydrology, low: np.ndarray) -> dict:
    import shapely

    df = _overture("roads", "theme=transportation/type=segment", ["names", "class", "geometry"],
                   lambda ds: (ds.field("subtype") == "road") & ds.field("class").isin(list(ROAD_CLASSES)))
    feats = []
    for _, r in df.iterrows():
        line = shapely.segmentize(shapely.from_wkb(r["geometry"]), 0.0002)  # a point every ~20 m
        xy = np.asarray(line.coords)
        name = (r["names"] or {}).get("primary") if isinstance(r["names"], dict) else None
        coords = [[round(x, 5), round(y, 5)] for x, y in xy]
        feats.append({"type": "Feature", "properties": {"kind": "road", "class": r["class"], "name": name},
                      "geometry": {"type": "LineString", "coordinates": coords}})
        rr, cc, ok = _cells(h, xy[:, 0], xy[:, 1])
        wet = ok & low[rr, cc]
        # Runs of consecutive points on low ground: stretches that may flood.
        start = None
        for i, w in enumerate(list(wet) + [False]):
            if w and start is None:
                start = max(i - 1, 0)
            elif not w and start is not None:
                piece = coords[start : min(i + 1, len(coords))]
                if len(piece) >= 2:
                    feats.append({"type": "Feature", "properties": {"kind": "low_road", "class": r["class"], "name": name},
                                  "geometry": {"type": "LineString", "coordinates": piece}})
                start = None
    return {"type": "FeatureCollection", "features": feats}


def facilities(h: terrain.Hydrology, low: np.ndarray, steep: np.ndarray) -> dict:
    import shapely

    wanted = [c for cats in FACILITY_GROUPS.values() for c in cats]
    df = _overture("places", "theme=places/type=place", ["names", "basic_category", "confidence", "geometry"],
                   lambda ds: ds.field("basic_category").isin(wanted))
    group_of = {c: g for g, cats in FACILITY_GROUPS.items() for c in cats}
    feats = []
    for _, r in df.iterrows():
        if (r["confidence"] or 0) < 0.5:
            continue
        p = shapely.from_wkb(r["geometry"])
        rr, cc, ok = _cells(h, np.array([p.x]), np.array([p.y]))
        if not ok[0]:
            continue
        name = r["names"].get("primary") if isinstance(r["names"], dict) else None
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(p.x, 5), round(p.y, 5)]},
                      "properties": {"group": group_of[r["basic_category"]], "category": r["basic_category"],
                                     "name": name, "low": bool(low[rr[0], cc[0]]), "steep": bool(steep[rr[0], cc[0]])}})
    return {"type": "FeatureCollection", "features": feats}


# --- building tiles ----------------------------------------------------------

def _merc(lon: np.ndarray, lat: np.ndarray, z: int) -> tuple[np.ndarray, np.ndarray]:
    """Global pixel coordinates (256-px tiles) at zoom z."""
    n = 256 * 2**z
    x = (lon + 180) / 360 * n
    s = np.sin(np.radians(lat))
    y = (0.5 - np.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def building_tiles(h: terrain.Hydrology, low: np.ndarray, steep: np.ndarray, out: Path) -> list[str]:
    """Footprints drawn into 256-px PNG tiles, coloured by the ground under them."""
    import shapely
    from PIL import Image, ImageDraw

    df = _overture("buildings", "theme=buildings/type=building", ["geometry"])
    geoms = shapely.from_wkb(df["geometry"].to_numpy())
    cent = shapely.centroid(geoms)
    cx, cy = shapely.get_x(cent), shapely.get_y(cent)
    rr, cc, ok = _cells(h, cx, cy)
    kind = np.where(ok & low[rr, cc], 1, np.where(ok & steep[rr, cc], 2, 0))
    colours = {0: NEUTRAL_RGB + (200,), 1: LOW_RGB + (235,), 2: STEEP_RGB + (235,)}
    outline = {0: (90, 96, 104, 220), 1: (20, 70, 150, 255), 2: (150, 60, 25, 255)}
    rings = [np.asarray(g.exterior.coords) if g.geom_type == "Polygon" else np.asarray(max(g.geoms, key=lambda q: q.area).exterior.coords)
             for g in geoms]
    written = []
    for z in BUILDING_ZOOMS:
        px, py = _merc(cx, cy, z)
        tx, ty = (px // 256).astype(int), (py // 256).astype(int)
        order = np.lexsort((ty, tx))
        keys = np.stack([tx[order], ty[order]], axis=1)
        splits = np.nonzero(np.any(np.diff(keys, axis=0) != 0, axis=1))[0] + 1
        for idx in np.split(order, splits):
            if len(idx) == 0:
                continue
            x0, y0 = tx[idx[0]] * 256, ty[idx[0]] * 256
            img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            for i in idx:
                if z <= 14:  # buildings are a pixel or two: draw them as dots
                    x, y = px[i] - x0, py[i] - y0
                    draw.rectangle([x - 0.5, y - 0.5, x + 0.5, y + 0.5], fill=colours[kind[i]])
                else:
                    gx, gy = _merc(rings[i][:, 0], rings[i][:, 1], z)
                    pts = list(zip(gx - x0, gy - y0))
                    if len(pts) >= 3:
                        draw.polygon(pts, fill=colours[kind[i]], outline=outline[kind[i]] if z >= 16 else None)
            path = out / "buildings" / str(z) / str(tx[idx[0]]) / f"{ty[idx[0]]}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            img.save(path, optimize=True)
            written.append(f"{z}/{tx[idx[0]]}/{ty[idx[0]]}")
        print(f"buildings z{z}: {sum(1 for w in written if w.startswith(f'{z}/'))} tiles", flush=True)
    return written


# --- run ---------------------------------------------------------------------

def run(out: Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    h = terrain.hydrology()
    low, steep = _masks(h)
    _png(hillshade(h), out / "hillshade.png")
    _png(_mask_rgba(low, LOW_RGB, 115), out / "lowground.png")
    _png(_mask_rgba(steep, STEEP_RGB, 120), out / "steep.png")
    _png(population_rgba(h), out / "population.png")
    print("rasters written", flush=True)
    (out / "streams.geojson").write_text(json.dumps(streams(h), separators=(",", ":")))
    print("streams written", flush=True)
    (out / "roads.geojson").write_text(json.dumps(roads(h, low), separators=(",", ":")))
    print("roads written", flush=True)
    (out / "facilities.geojson").write_text(json.dumps(facilities(h, low, steep), separators=(",", ":")))
    print("facilities written", flush=True)
    tiles = building_tiles(h, low, steep, out)
    meta = {"bounds": _bounds(h), "building_zooms": [min(BUILDING_ZOOMS), max(BUILDING_ZOOMS)], "building_tiles": tiles,
            "population_steps": POP_STEPS,
            "colours": {"low": "#%02x%02x%02x" % LOW_RGB, "steep": "#%02x%02x%02x" % STEEP_RGB,
                        "neutral": "#%02x%02x%02x" % NEUTRAL_RGB}}
    (out / "layers.json").write_text(json.dumps(meta, separators=(",", ":")))
    return meta
