"""Warning zones: one per stream catchment that reaches the sea.

A flash flood is a catchment-scale event: rain anywhere upstream ends up at the
same outlet. So each catchment draining at least ``MIN_ZONE_KM2`` to the sea
or estuary becomes a warning zone. For each zone we record:

* how much **low ground near streams** it has (height above stream < 3 m and
  elevation < 20 m): where stream and coastal flooding happens;
* how much **steep hillside** it has (slope > 25 deg): where runoff, landslides
  and wall collapses happen;
* which places in the flood history fall inside it;
* which CHIRPS rainfall cells cover it, so rain can be averaged per zone.

Land outside every such catchment (short coastal slopes) is zone 0, "coastal
fringe".
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import requests

from floodwatch import config, terrain
from floodwatch.sources.http import USER_AGENT

MIN_ZONE_KM2 = 1.0
LOW_HAND_M, LOW_ELEV_M = 3.0, 20.0
STEEP_DEG = 25.0
CHIRPS_RES = 0.05
CITY = (-13.31, 8.39, -13.13, 8.51)  # west, south, east, north: where flood reports are
REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
REVERSE_CACHE = config.RAW_DIR / "reverse_geocode.json"
FIG = config.REPO_ROOT / "docs" / "analysis" / "figures" / "warning_zones.png"


def outlets(h: terrain.Hydrology) -> list[tuple[int, int]]:
    """Cells draining >= MIN_ZONE_KM2 whose water leaves the land (or stops)."""
    rows, cols = np.nonzero(h.land & (h.upstream_km2 >= MIN_ZONE_KM2))
    height, width = h.dem.shape
    found = []
    for r, c in zip(rows, cols):
        code = int(h.fdir[r, c])
        if code not in terrain.D8_OFFSETS:  # flat or pit: water stops here
            found.append((r, c))
            continue
        dr, dc = terrain.D8_OFFSETS[code]
        rr, cc = r + dr, c + dc
        if not (0 <= rr < height and 0 <= cc < width) or not h.land[rr, cc]:
            found.append((r, c))
    return sorted(found, key=lambda rc: -h.upstream_km2[rc])


def label(h: terrain.Hydrology) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Raster of zone ids (0 = coastal fringe, -1 = sea) and the outlet of each zone."""
    labels = np.where(h.land, 0, -1).astype("int32")
    kept: list[tuple[int, int]] = []
    for r, c in outlets(h):
        if labels[r, c] > 0:  # already inside a bigger zone
            continue
        mask = np.asarray(h.grid.catchment(x=c, y=r, fdir=h.fdir_raster, xytype="index")) > 0
        new = mask & (labels == 0)
        if new.sum() * h.cell_km2 < MIN_ZONE_KM2:
            continue
        kept.append((r, c))
        labels[new] = len(kept)
    return labels, kept


def _reverse_name(lat: float, lon: float, cache: dict) -> str:
    key = f"{lat:.5f},{lon:.5f}"
    if key not in cache:
        import time

        resp = requests.get(
            REVERSE_URL,
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 16},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        addr = resp.json().get("address", {})
        cache[key] = next(
            (addr[k] for k in ("neighbourhood", "quarter", "suburb", "village", "hamlet", "town", "city_district") if k in addr),
            "",
        )
        REVERSE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        REVERSE_CACHE.write_text(json.dumps(cache, indent=1))
        time.sleep(1.1)
    return cache[key]


def _zone_at(labels: np.ndarray, h: terrain.Hydrology, lon: float, lat: float, radius: int = 8) -> int:
    """Zone of the biggest stream within ~250 m of a place (that is where its
    floodwater comes from); the coastal fringe if no zone stream is that close."""
    col, row = ~h.transform * (lon, lat)
    r, c = int(row), int(col)
    r0, c0 = max(r - radius, 0), max(c - radius, 0)
    zone = labels[r0 : r + radius + 1, c0 : c + radius + 1]
    area = np.where(zone > 0, h.upstream_km2[r0 : r + radius + 1, c0 : c + radius + 1], -1.0)
    if area.max() > 0:
        return int(zone.flat[area.argmax()])
    return 0 if (zone >= 0).any() else -1


def build() -> dict:
    terrain.download_dem()
    h = terrain.hydrology()
    labels, outs = label(h)
    slope = h.slope_deg()
    low = h.land & (np.nan_to_num(h.hand, nan=99) < LOW_HAND_M) & (h.dem < LOW_ELEV_M)
    steep = h.land & (np.nan_to_num(slope) > STEEP_DEG)

    places = pd.read_csv(config.DERIVED_DIR / "flood_places.csv")
    places = places[places["geocoded"]].copy()
    places["zone"] = [_zone_at(labels, h, lo, la) for lo, la in zip(places["lon"], places["lat"])]

    cache: dict = json.loads(REVERSE_CACHE.read_text()) if REVERSE_CACHE.exists() else {}
    rows = []
    for zone_id in range(0, len(outs) + 1):
        cells = labels == zone_id
        here = places[places["zone"] == zone_id]
        if zone_id == 0:
            name, olat, olon, in_city = "Coastal fringe (short slopes draining straight to the sea)", None, None, True
        else:
            r, c = outs[zone_id - 1]
            olon, olat = h.transform * (c + 0.5, r + 0.5)
            in_city = CITY[0] <= olon <= CITY[2] and CITY[1] <= olat <= CITY[3]
            near = here.sort_values("events", ascending=False)["place"].tolist()
            name = near[0] if near else (_reverse_name(olat, olon, cache) if in_city else "")
            name = (name.title() if name.isupper() else name) or f"Unnamed zone {zone_id}"
        rows.append(
            {
                "zone_id": zone_id,
                "name": name,
                "outlet_lat": None if olat is None else round(olat, 5),
                "outlet_lon": None if olon is None else round(olon, 5),
                "in_city": bool(in_city),
                "area_km2": round(float(cells.sum() * h.cell_km2), 2),
                "max_elev_m": round(float(h.dem[cells].max()), 0),
                "low_ground_km2": round(float((cells & low).sum() * h.cell_km2), 3),
                "steep_km2": round(float((cells & steep).sum() * h.cell_km2), 3),
                "flood_places": " | ".join(here["place"]),
                "flood_place_mentions": int(here["events"].sum()),
            }
        )
    zones = pd.DataFrame(rows)
    dup = zones["name"].duplicated(keep="first") & (zones["zone_id"] > 0)
    zones.loc[dup, "name"] = zones.loc[dup, "name"] + " (zone " + zones.loc[dup, "zone_id"].astype(str) + ")"
    zones["steep_share"] = (zones["steep_km2"] / zones["area_km2"]).round(3)

    config.DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    zones.to_csv(config.DERIVED_DIR / "zones.csv", index=False)
    _write_geojson(labels, h, zones)
    _write_chirps_weights(labels, h)
    _plot(labels, h, zones, places)
    summary = {
        "zones": int(len(outs)),
        "city_zones": int(zones.loc[zones["zone_id"] > 0, "in_city"].sum()),
        "zones_with_reported_floods": int((zones["flood_place_mentions"] > 0).sum()),
        "figure": str(FIG.relative_to(config.REPO_ROOT)),
    }
    print(json.dumps(summary, indent=2))
    return summary


def zone_daily_rain(cells: pd.DataFrame) -> pd.DataFrame:
    """Daily CHIRPS rain per zone (columns = zone ids), area-weighted."""
    weights = pd.read_csv(config.DERIVED_DIR / "zone_chirps_weights.csv")
    cells = cells[cells["precip_mm"] >= 0]
    merged = weights.merge(cells, on=["lat", "lon"], how="inner")
    merged["w_rain"] = merged["weight"] * merged["precip_mm"]
    num = merged.groupby(["date", "zone_id"])["w_rain"].sum()
    den = merged.groupby(["date", "zone_id"])["weight"].sum()  # < 1 where a cell is sea in CHIRPS
    return (num / den).unstack("zone_id")


def resolution_check(first_year: int = 2008) -> dict:
    """Does zone-averaged rain flag floods better than the peninsula average?

    For every (flood, zone) pair, where the zone holds a place named in that
    flood, compare the flood window's rain percentile using (a) that zone's own
    rain and (b) the peninsula average, each against its own rainy-season days.
    """
    from floodwatch import events, hindcast
    from floodwatch.sources import chirps

    cells = chirps.fetch(first_year, pd.Timestamp.today().year)
    per_zone = zone_daily_rain(cells)
    peninsula = chirps.daily_features(cells)["day_mean"]
    places = pd.read_csv(config.DERIVED_DIR / "flood_places.csv")
    zones = pd.read_csv(config.DERIVED_DIR / "zones.csv")
    h = terrain.hydrology()
    labels, _ = label(h)
    place_zone = {
        p: _zone_at(labels, h, lo, la)
        for p, lo, la in places.loc[places["geocoded"], ["place", "lon", "lat"]].itertuples(index=False)
    }

    cat = events.load_catalogue()
    cat = cat[cat["date_confidence"].isin(["exact", "approx_day"]) & (cat["date"].dt.year >= first_year)]

    def pct(series: pd.Series, day: pd.Timestamp) -> float:
        s = series[hindcast.in_season(pd.DatetimeIndex(series.index))]
        w = hindcast.window_max(s)
        v = w.get(day, np.nan)
        ref = w.dropna().to_numpy()
        return float((ref <= v).mean() * 100) if pd.notna(v) else float("nan")

    pairs = []
    for _, ev in cat.iterrows():
        for z in sorted({place_zone[p] for p in ev["locations"] if p in place_zone and place_zone[p] > 0}):
            if z in per_zone:
                pairs.append(
                    {
                        "flood": str(ev["date"].date()),
                        "zone_id": z,
                        "zone": zones.set_index("zone_id").at[z, "name"],
                        "zone_rain_pct": round(pct(per_zone[z], ev["date"]), 1),
                        "peninsula_rain_pct": round(pct(peninsula, ev["date"]), 1),
                    }
                )
    df = pd.DataFrame(pairs)
    out = {
        "pairs": len(df),
        "mean_percentile_zone_rain": round(float(df["zone_rain_pct"].mean()), 1),
        "mean_percentile_peninsula_rain": round(float(df["peninsula_rain_pct"].mean()), 1),
        "zone_better_in": int((df["zone_rain_pct"] > df["peninsula_rain_pct"]).sum()),
        "detail": df.to_dict(orient="records"),
    }
    (config.DERIVED_DIR / "zone_resolution_check.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "detail"}, indent=2))
    print(df.to_string(index=False))
    return out


def _write_geojson(labels: np.ndarray, h: terrain.Hydrology, zones: pd.DataFrame) -> None:
    from rasterio import features
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    parts: dict[int, list] = {}
    for geom, value in features.shapes(labels, mask=labels >= 0, transform=h.transform):
        parts.setdefault(int(value), []).append(shape(geom))
    feats = []
    for _, z in zones.iterrows():
        geoms = parts.get(int(z["zone_id"]))
        if not geoms:
            continue
        geom = unary_union(geoms).simplify(0.0002, preserve_topology=True)
        props = {k: (None if pd.isna(v) else v) for k, v in z.items()}
        feats.append({"type": "Feature", "properties": props, "geometry": mapping(geom)})
    path = config.DERIVED_DIR / "zones.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, default=float))


def _write_chirps_weights(labels: np.ndarray, h: terrain.Hydrology) -> None:
    """Share of each zone falling in each CHIRPS 0.05 deg cell."""
    rows, cols = np.nonzero(labels >= 0)
    lon, lat = h.transform * (cols + 0.5, rows + 0.5)
    cell_lon = (np.floor(np.asarray(lon) / CHIRPS_RES) * CHIRPS_RES + CHIRPS_RES / 2).round(3)
    cell_lat = (np.floor(np.asarray(lat) / CHIRPS_RES) * CHIRPS_RES + CHIRPS_RES / 2).round(3)
    df = pd.DataFrame({"zone_id": labels[rows, cols], "lat": cell_lat, "lon": cell_lon})
    w = df.groupby(["zone_id", "lat", "lon"]).size().rename("n").reset_index()
    w["weight"] = (w["n"] / w.groupby("zone_id")["n"].transform("sum")).round(4)
    w.drop(columns="n").to_csv(config.DERIVED_DIR / "zone_chirps_weights.csv", index=False)


def _plot(labels: np.ndarray, h: terrain.Hydrology, zones: pd.DataFrame, places: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource, ListedColormap

    FIG.parent.mkdir(parents=True, exist_ok=True)
    t = h.transform
    extent = (t.c, t.c + t.a * labels.shape[1], t.f + t.e * labels.shape[0], t.f)
    fig, ax = plt.subplots(figsize=(11, 8), dpi=150)
    ax.set_facecolor("#dbe9f4")
    dem = np.where(h.land, h.dem, 0.0)
    shade = LightSource(azdeg=315, altdeg=45).hillshade(dem, vert_exag=3)
    ax.imshow(np.where(h.land, shade, np.nan), extent=extent, cmap="gray", vmin=0, vmax=1.3)

    rng = np.random.default_rng(3)
    palette = plt.get_cmap("tab20")(np.linspace(0, 1, 20))
    colors = palette[rng.permutation(len(zones) + 1) % 20]
    zone_rgba = np.where(labels[..., None] > 0, colors[np.clip(labels, 0, None)], np.nan)
    ax.imshow(zone_rgba, extent=extent, alpha=0.38, interpolation="nearest")

    # Zone borders: cells whose right or lower neighbour is in another zone.
    edge = np.zeros(labels.shape, bool)
    edge[:, :-1] |= labels[:, :-1] != labels[:, 1:]
    edge[:-1, :] |= labels[:-1, :] != labels[1:, :]
    edge &= h.land
    ax.imshow(np.where(edge, 1.0, np.nan), extent=extent, cmap=ListedColormap(["#333333"]), interpolation="nearest")

    low = h.land & (np.nan_to_num(h.hand, nan=99) < LOW_HAND_M) & (h.dem < LOW_ELEV_M)
    ax.imshow(np.where(low, 1.0, np.nan), extent=extent, cmap=ListedColormap(["#1f5fa8"]), alpha=0.75, interpolation="nearest")

    ax.scatter(places["lon"], places["lat"], s=30 + 40 * places["events"], c="#c0392b",
               edgecolor="white", linewidth=0.9, zorder=3)
    city = zones[(zones["zone_id"] > 0) & zones["in_city"]]
    for _, z in city.iterrows():
        if z["area_km2"] >= 2 or z["flood_place_mentions"] > 0:
            ax.annotate(f"{z['zone_id']}", (z["outlet_lon"], z["outlet_lat"]), fontsize=7, weight="bold",
                        ha="center", va="center", color="#111",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#555", lw=0.5))
    ax.set_xlim(CITY[0], CITY[2])
    ax.set_ylim(CITY[1], CITY[3])
    ax.set_title("Freetown warning zones v0: one per stream catchment (coloured), low ground near streams (dark blue), "
                 "reported flood places (red). Numbers mark zone outlets.", fontsize=8)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    fig.savefig(FIG, bbox_inches="tight")
    plt.close(fig)
