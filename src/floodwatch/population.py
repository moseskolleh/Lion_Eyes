"""Who is exposed: buildings and people per warning zone and hazard class.

* Buildings: Overture Maps (merges Google, Microsoft and OpenStreetMap
  footprints), read from its public S3 bucket with PyArrow, keeping only the
  peninsula. Each building is placed at the centre of its bounding box.
* People: Meta / CIESIN High Resolution Settlement Layer (HRSL), ~30 m,
  read as a window from the public cloud-optimised GeoTIFF mosaic.

Both are put on the 1-arcsecond elevation grid used for the zones, then
counted per zone overall, on low ground near streams (HAND < 3 m, elevation
< 20 m) and on steep slopes (> 25 deg). Counts are estimates: HRSL spreads a
census total over detected buildings, and footprints miss some new or small
structures.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from floodwatch import config, terrain, zones

OVERTURE_RELEASE = "2026-11-18.0"
OVERTURE_PATH = f"overturemaps-us-west-2/release/{OVERTURE_RELEASE}/theme=buildings/type=building/"
HRSL_VRT = "https://dataforgood-fb-data.s3.amazonaws.com/hrsl-cogs/hrsl_general/hrsl_general-latest.vrt"
BUILDINGS_CACHE = config.RAW_DIR / "buildings_overture.csv.gz"
POPULATION_CACHE = config.RAW_DIR / "hrsl_peninsula.npy"


def buildings() -> pd.DataFrame:
    """Centre (lon, lat) of every Overture building over the peninsula."""
    if BUILDINGS_CACHE.exists():
        return pd.read_csv(BUILDINGS_CACHE)
    import pyarrow.dataset as ds
    import pyarrow.fs as pafs

    west, south, east, north = terrain.BOUNDS
    data = ds.dataset(OVERTURE_PATH, filesystem=pafs.S3FileSystem(anonymous=True, region="us-west-2"), format="parquet")
    xmin, ymin = ds.field("bbox", "xmin"), ds.field("bbox", "ymin")
    table = data.to_table(columns=["bbox"], filter=(xmin >= west) & (xmin <= east) & (ymin >= south) & (ymin <= north))
    bbox = table.column("bbox").combine_chunks()
    df = pd.DataFrame(
        {
            "lon": ((bbox.field("xmin").to_numpy() + bbox.field("xmax").to_numpy()) / 2).round(6),
            "lat": ((bbox.field("ymin").to_numpy() + bbox.field("ymax").to_numpy()) / 2).round(6),
        }
    )
    BUILDINGS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(BUILDINGS_CACHE, index=False)
    return df


def population(h: terrain.Hydrology) -> np.ndarray:
    """HRSL people per cell, resampled onto the elevation grid of ``h``."""
    if POPULATION_CACHE.exists():
        grid = np.load(POPULATION_CACHE)
        if grid.shape == h.dem.shape:
            return grid
    import rasterio
    from rasterio.warp import Resampling, reproject

    grid = np.zeros(h.dem.shape, dtype="float64")
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT="60"):
        with rasterio.open(f"/vsicurl/{HRSL_VRT}") as src:
            reproject(
                source=rasterio.band(src, 1), destination=grid, dst_transform=h.transform,
                dst_crs="EPSG:4326", resampling=Resampling.sum, src_nodata=np.nan, dst_nodata=0,
            )
    grid = np.where(np.isfinite(grid) & (grid > 0), grid, 0.0)
    POPULATION_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.save(POPULATION_CACHE, grid)
    return grid


def building_counts(h: terrain.Hydrology, b: pd.DataFrame) -> np.ndarray:
    """Number of buildings whose centre falls in each grid cell."""
    cols, rows = (~h.transform) @ (b["lon"].to_numpy(), b["lat"].to_numpy())
    rows, cols = np.floor(rows).astype(int), np.floor(cols).astype(int)
    ok = (rows >= 0) & (rows < h.dem.shape[0]) & (cols >= 0) & (cols < h.dem.shape[1])
    counts = np.zeros(h.dem.shape, dtype="int32")
    np.add.at(counts, (rows[ok], cols[ok]), 1)
    return counts


def zone_exposure() -> pd.DataFrame:
    """Buildings and people per zone: total, on low ground, on steep slopes."""
    h = terrain.hydrology()
    labels, _ = zones.label(h)
    low = h.land & (np.nan_to_num(h.hand, nan=99) < zones.LOW_HAND_M) & (h.dem < zones.LOW_ELEV_M)
    steep = h.land & (np.nan_to_num(h.slope_deg()) > zones.STEEP_DEG)
    people = population(h)
    blds = building_counts(h, buildings())

    n = labels.max() + 1
    lab = np.where(labels >= 0, labels, n)  # sea -> an extra bin we drop

    def per_zone(values: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
        v = values if mask is None else np.where(mask, values, 0)
        return np.bincount(lab.ravel(), weights=v.ravel().astype("float64"), minlength=n + 1)[:n]

    out = pd.DataFrame(
        {
            "zone_id": np.arange(n),
            "people": per_zone(people).round(0),
            "people_low_ground": per_zone(people, low).round(0),
            "people_steep": per_zone(people, steep).round(0),
            "buildings": per_zone(blds).round(0),
            "buildings_low_ground": per_zone(blds, low).round(0),
            "buildings_steep": per_zone(blds, steep).round(0),
        }
    ).astype({c: "int64" for c in ("people", "people_low_ground", "people_steep",
                                   "buildings", "buildings_low_ground", "buildings_steep")})
    return out


def run() -> pd.DataFrame:
    """Add exposure columns to zones.csv and zones.geojson."""
    import json

    exp = zone_exposure()
    path = config.DERIVED_DIR / "zones.csv"
    z = pd.read_csv(path)
    z = z.drop(columns=[c for c in exp.columns if c != "zone_id" and c in z.columns]).merge(exp, on="zone_id", how="left")
    z.to_csv(path, index=False)

    gj_path = config.DERIVED_DIR / "zones.geojson"
    gj = json.loads(gj_path.read_text())
    by_id = exp.set_index("zone_id").to_dict(orient="index")
    for f in gj["features"]:
        f["properties"].update({k: int(v) for k, v in by_id.get(f["properties"]["zone_id"], {}).items()})
    gj_path.write_text(json.dumps(gj))

    city = z[z["in_city"]]
    print(
        f"peninsula: {int(z['people'].sum()):,} people, {int(z['buildings'].sum()):,} buildings; "
        f"on low ground near streams: {int(z['people_low_ground'].sum()):,} people, "
        f"{int(z['buildings_low_ground'].sum()):,} buildings; "
        f"on steep slopes: {int(z['people_steep'].sum()):,} people"
    )
    print(city.sort_values("people_low_ground", ascending=False)
          [["zone_id", "name", "people", "people_low_ground", "buildings_low_ground", "people_steep"]].head(12).to_string(index=False))
    return z
