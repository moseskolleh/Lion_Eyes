"""Where past floods happened, on the terrain.

Geocodes every neighbourhood named in the flood history, samples the terrain
there (elevation, height above nearest stream, size of the nearby stream), and
compares it with ordinary low-lying land, to test whether "low and next to a
big stream" describes Freetown's flood places.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from floodwatch import config, events, geocode, terrain

FIG_DIR = config.REPO_ROOT / "docs" / "analysis" / "figures"


def flood_places(hydro: terrain.Hydrology) -> pd.DataFrame:
    catalogue = events.load_catalogue()
    counts = Counter(name.strip() for locs in catalogue["locations"] for name in locs if name.strip())
    found = geocode.lookup(sorted(counts))
    rows = []
    for name, n in counts.items():
        hit = found.get(name)
        if not hit:
            rows.append({"place": name, "events": n, "geocoded": False})
            continue
        rows.append(
            {
                "place": name,
                "events": n,
                "geocoded": True,
                "lat": round(hit["lat"], 5),
                "lon": round(hit["lon"], 5),
                "osm_type": hit["osm_type"],
                "coastal": events.is_coastal([name]),
                **hydro.sample(hit["lon"], hit["lat"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["events", "place"], ascending=[False, True])


def lowland_baseline(hydro: terrain.Hydrology, max_elev: float = 150.0, n: int = 5000) -> pd.DataFrame:
    """Random land cells below ``max_elev`` (roughly where people live)."""
    rng = np.random.default_rng(0)
    rows, cols = np.nonzero((hydro.dem != terrain.NODATA) & (hydro.dem < max_elev))
    pick = rng.choice(len(rows), size=min(n, len(rows)), replace=False)
    samples = []
    for i in pick:
        lon, lat = hydro.transform * (cols[i] + 0.5, rows[i] + 0.5)
        samples.append(hydro.sample(lon, lat))
    return pd.DataFrame(samples)


def plot(hydro: terrain.Hydrology, places: pd.DataFrame) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    land = hydro.dem != terrain.NODATA
    dem = np.where(land, hydro.dem, np.nan)
    t = hydro.transform
    extent = (t.c, t.c + t.a * dem.shape[1], t.f + t.e * dem.shape[0], t.f)

    fig, ax = plt.subplots(figsize=(11, 8), dpi=150)
    ax.set_facecolor("#dbe9f4")  # sea
    shade = LightSource(azdeg=315, altdeg=45).hillshade(np.nan_to_num(dem, nan=0.0), vert_exag=3)
    ax.imshow(np.where(land, shade, np.nan), extent=extent, cmap="gray", vmin=0, vmax=1.3)
    ax.imshow(dem, extent=extent, cmap="YlOrBr", vmin=0, vmax=700, alpha=0.45)

    # Streams on land draining >= 1 km2, thickened by one cell so they show.
    big = land & (hydro.upstream_km2 >= 1.0)
    thick = big.copy()
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        thick |= np.roll(big, (dr, dc), axis=(0, 1))
    ax.imshow(np.where(thick & land, 1.0, np.nan), extent=extent, cmap="Blues", vmin=0, vmax=1, interpolation="nearest")

    geo = places[places["geocoded"]]
    ax.scatter(geo["lon"], geo["lat"], s=30 + 40 * geo["events"], c="#c0392b",
               edgecolor="white", linewidth=0.9, zorder=3)
    for _, r in geo.iterrows():
        ax.annotate(r["place"], (r["lon"], r["lat"]), xytext=(5, 3), textcoords="offset points",
                    fontsize=7, color="#222")
    ax.set_xlim(-13.31, -13.13)  # the city, where reported floods are
    ax.set_ylim(8.39, 8.51)
    ax.set_title("Freetown: streams draining 1 km² or more (blue) and reported flood places "
                 "(red, sized by number of events, 2007-2026)", fontsize=9)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    out = FIG_DIR / "streams_and_flood_places.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return str(out.relative_to(config.REPO_ROOT))


def run() -> dict:
    terrain.download_dem()
    hydro = terrain.hydrology()
    places = flood_places(hydro)
    config.DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    places.to_csv(config.DERIVED_DIR / "flood_places.csv", index=False)
    base = lowland_baseline(hydro)
    geo = places[places["geocoded"] & places["hand_m"].notna()]

    def share(df: pd.DataFrame, col: str, op, value: float) -> float:
        s = df[col].dropna()
        return round(float(op(s, value).mean()), 3) if len(s) else float("nan")

    summary = {
        "places_named": int(len(places)),
        "places_geocoded": int(places["geocoded"].sum()),
        "flood_places_median_hand_m": round(float(geo["hand_m"].median()), 1),
        "lowland_median_hand_m": round(float(base["hand_m"].median()), 1),
        "flood_places_share_hand_below_5m": share(geo, "hand_m", np.less, 5.0),
        "lowland_share_hand_below_5m": share(base, "hand_m", np.less, 5.0),
        "flood_places_median_elev_m": round(float(geo["elevation_m"].median()), 1),
        "lowland_median_elev_m": round(float(base["elevation_m"].median()), 1),
        "flood_places_median_stream_km2": round(float(geo["nearby_stream_km2"].median()), 2),
        "lowland_median_stream_km2": round(float(base["nearby_stream_km2"].median()), 2),
        "figure": plot(hydro, places),
    }
    import json

    (config.DERIVED_DIR / "exposure_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary
