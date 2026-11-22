"""Where the water goes: streams, catchment size and height above stream.

Uses the free Copernicus 30 m elevation model. From it we trace how water
flows downhill (D8 flow directions), how much land drains through each point
(upstream area), where streams form, and each point's height above the nearest
stream (HAND). Low HAND near a big stream is where flash floods arrive first.

Caveat: the Copernicus model is a surface model (it includes roofs and trees),
and city drains and culverts are invisible to it, so in dense neighbourhoods
the traced paths are approximate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from floodwatch.config import RAW_DIR

DEM_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_N08_00_W014_00_DEM/Copernicus_DSM_COG_10_N08_00_W014_00_DEM.tif"
)
BOUNDS = (-13.32, 8.20, -12.98, 8.56)  # west, south, east, north
DEM_PATH = RAW_DIR / "dem" / "freetown_dem.tif"
NODATA = -9999.0
STREAM_MIN_KM2 = 0.25  # land draining through a cell before we call it a stream


def download_dem(path: Path = DEM_PATH) -> Path:
    """Cut the peninsula out of the 1x1 degree Copernicus tile; sea -> nodata."""
    if path.exists():
        return path
    import rasterio
    from rasterio.windows import from_bounds

    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"), rasterio.open(f"/vsicurl/{DEM_URL}") as src:
        window = from_bounds(*BOUNDS, src.transform).round_offsets().round_lengths()
        dem = src.read(1, window=window).astype("float32")
        transform = src.window_transform(window)
        profile = src.profile | {
            "height": dem.shape[0], "width": dem.shape[1], "transform": transform,
            "nodata": NODATA, "dtype": "float32", "compress": "deflate", "tiled": False,
        }
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
    dem[dem <= 0.0] = NODATA  # sea and estuary are flattened to 0 in this model
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(dem, 1)
    return path


@dataclass
class Hydrology:
    dem: np.ndarray
    upstream_km2: np.ndarray
    streams: np.ndarray
    hand: np.ndarray
    transform: object  # affine.Affine

    def sample(self, lon: float, lat: float) -> dict:
        col, row = ~self.transform * (lon, lat)
        r, c = int(row), int(col)
        if not (0 <= r < self.dem.shape[0] and 0 <= c < self.dem.shape[1]):
            return {}
        if self.dem[r, c] == NODATA:  # point on water (e.g. a bay): nearest land within ~300 m
            rr, cc = np.nonzero(self.dem[max(r - 10, 0) : r + 11, max(c - 10, 0) : c + 11] != NODATA)
            if len(rr) == 0:
                return {}
            k = np.argmin((rr + max(r - 10, 0) - r) ** 2 + (cc + max(c - 10, 0) - c) ** 2)
            r, c = rr[k] + max(r - 10, 0), cc[k] + max(c - 10, 0)
        # Nearby-stream size: the biggest upstream area within ~150 m.
        r0, r1, c0, c1 = max(r - 5, 0), r + 6, max(c - 5, 0), c + 6
        near = np.where(self.streams[r0:r1, c0:c1], self.upstream_km2[r0:r1, c0:c1], 0)
        return {
            "elevation_m": float(self.dem[r, c]) if self.dem[r, c] != NODATA else None,
            "hand_m": None if np.isnan(self.hand[r, c]) else float(self.hand[r, c]),
            "nearby_stream_km2": float(near.max()) if near.size else 0.0,
        }


def hydrology(path: Path = DEM_PATH) -> Hydrology:
    from pysheds.grid import Grid

    grid = Grid.from_raster(str(path), nodata=NODATA)
    dem = grid.read_raster(str(path), nodata=NODATA)
    conditioned = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)))
    fdir = grid.flowdir(conditioned)
    acc = grid.accumulation(fdir)

    lat = (BOUNDS[1] + BOUNDS[3]) / 2
    cell_km2 = (grid.affine.a * 111.32 * np.cos(np.radians(lat))) * (-grid.affine.e * 110.57)
    upstream_km2 = np.asarray(acc) * cell_km2
    stream_mask = acc >= STREAM_MIN_KM2 / cell_km2  # stays a pysheds Raster
    streams = np.asarray(stream_mask, dtype=bool)
    hand = np.asarray(grid.compute_hand(fdir, dem, stream_mask), dtype="float64")
    land = np.asarray(dem) != NODATA
    # Land that drains straight to the sea gets its height measured against the
    # sea cell's nodata value; its true height above drainage is its elevation.
    to_sea = land & (hand > 2000)
    hand[to_sea] = np.asarray(dem)[to_sea]
    hand[~land] = np.nan
    return Hydrology(np.asarray(dem), upstream_km2, streams, hand, grid.affine)
