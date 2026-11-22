"""Half-hourly rain around past floods (NASA IMERG): timing, intensity, skill.

Questions:
1. When, within the flood window, did the heaviest rain fall, and how does
   that compare with the reported flood time? (How much warning was possible?)
2. Do short-duration intensities (1-6 hour totals) separate flood windows from
   ordinary days better than daily totals do?
3. The hardest test: do they separate floods from *very wet days that did not
   (as far as we know) flood*?

Windows are three calendar days (UTC) centred on each date, as in the daily
hindcast, and controls get exactly the same treatment.
"""

from __future__ import annotations

import json
from datetime import timedelta

import numpy as np
import pandas as pd

from floodwatch import config, events, hindcast
from floodwatch.sources import imerg

# IMERG cells over peninsula land (cell centres); the 8.55 N row is mostly water.
PEN_LATS = (8.25, 8.35, 8.45)
PEN_LONS = (-13.25, -13.15, -13.05)
DURATIONS_H = {"max_1h": 1, "max_3h": 3, "max_6h": 6, "max_24h": 24}
FIG = config.REPO_ROOT / "docs" / "analysis" / "figures" / "flood_rain_timelines.png"


def flood_dates(first_year: int = 2008) -> pd.DataFrame:
    cat = events.load_catalogue()
    cat = cat[cat["date_confidence"].isin(["exact", "approx_day"]) & (cat["date"].dt.year >= first_year)]
    return cat[["event_id", "date", "time_of_day", "type", "coastal"]].reset_index(drop=True)


def control_dates(n_heavy: int = 30, n_random: int = 30, seed: int = 7) -> pd.DataFrame:
    """Very wet non-flood days (by CHIRPS) and random ordinary rainy-season days."""
    daily = pd.read_csv(config.DERIVED_DIR / "daily_features_chirps.csv", parse_dates=["date"]).set_index("date")
    daily = daily[hindcast.in_season(pd.DatetimeIndex(daily.index))].dropna(subset=["day_mean"])
    floods = pd.DatetimeIndex(flood_dates()["date"])
    far = pd.Series(True, index=daily.index)
    for e in floods:
        far.loc[e - pd.Timedelta(days=4) : e + pd.Timedelta(days=4)] = False
    pool = daily[far]
    heavy: list[pd.Timestamp] = []
    for d in pool.sort_values("day_mean", ascending=False).index:
        if all(abs((d - p).days) > 4 for p in heavy):
            heavy.append(d)
        if len(heavy) == n_heavy:
            break
    rest = pool.drop(index=[d for d in pool.index if any(abs((d - h).days) <= 4 for h in heavy)])
    rng = np.random.default_rng(seed)
    random_days = sorted(rng.choice(rest.index.to_numpy(), size=n_random, replace=False))
    return pd.DataFrame(
        {"date": list(heavy) + [pd.Timestamp(d) for d in random_days],
         "group": ["heavy_no_flood"] * len(heavy) + ["ordinary"] * n_random}
    )


def window_days(dates: pd.Series) -> list:
    return sorted({(d + timedelta(days=k)).date() for d in pd.to_datetime(dates) for k in (-1, 0, 1)})


def _half_hourly_mm(hh: pd.DataFrame) -> pd.DataFrame:
    sub = hh[hh["lat"].isin(PEN_LATS) & hh["lon"].isin(PEN_LONS)].copy()
    sub["mm"] = sub["rate_mm_h"] * 0.5
    wide = sub.pivot_table(index="time", columns=["lat", "lon"], values="mm")
    return wide.reindex(pd.date_range(wide.index.min(), wide.index.max(), freq="30min"))


def window_metrics(day: pd.Timestamp) -> dict:
    """Max 1/3/6/24 h totals on the wettest cell over [day-1, day+1], and when
    the heaviest 3 hours ended."""
    days = [(day + timedelta(days=k)).date() for k in (-1, 0, 1)]
    wide = _half_hourly_mm(imerg.fetch_days(days))
    out: dict = {}
    for key, hours in DURATIONS_H.items():
        roll = wide.rolling(2 * hours, min_periods=2 * hours).sum().max(axis=1)
        out[key] = round(float(roll.max()), 1)
        if key == "max_3h":
            out["peak_3h_ends"] = str(roll.idxmax() + pd.Timedelta(minutes=30))
    out["max_24h_mean"] = round(float(wide.mean(axis=1).rolling(48, min_periods=48).sum().max()), 1)
    out["product"] = "final"
    return out


def run() -> dict:
    floods = flood_dates()
    controls = control_dates()
    rows = []
    for _, f in floods.iterrows():
        rows.append({"date": f["date"], "group": "flood", "event_id": f["event_id"],
                     "time_of_day": f["time_of_day"], **window_metrics(f["date"])})
    for _, c in controls.iterrows():
        rows.append({"date": c["date"], "group": c["group"], **window_metrics(c["date"])})
    df = pd.DataFrame(rows)

    chirps = pd.read_csv(config.DERIVED_DIR / "daily_features_chirps.csv", parse_dates=["date"]).set_index("date")
    df["chirps_day_mean"] = [
        round(float(hindcast.window_max(chirps["day_mean"]).get(d, np.nan)), 1) for d in df["date"]
    ]

    metrics = list(DURATIONS_H) + ["max_24h_mean", "chirps_day_mean"]
    fl = df[df["group"] == "flood"]
    skill = {}
    for m in metrics:
        skill[m] = {}
        for other in ("ordinary", "heavy_no_flood"):
            neg = df.loc[df["group"] == other, m].to_numpy(dtype=float)
            pos = fl[m].to_numpy(dtype=float)
            skill[m][f"auc_vs_{other}"] = round(hindcast.auc(pos, neg), 3)
            skill[m][f"auc_vs_{other}_90pct"] = hindcast.auc_interval(pos, neg)
        skill[m]["median"] = {g: round(float(df.loc[df["group"] == g, m].median()), 1)
                              for g in ("flood", "heavy_no_flood", "ordinary")}

    out = {
        "floods": int(len(fl)),
        "heavy_no_flood": int((df["group"] == "heavy_no_flood").sum()),
        "ordinary": int((df["group"] == "ordinary").sum()),
        "skill": skill,
        "windows": df.assign(date=df["date"].dt.date.astype(str)).to_dict(orient="records"),
    }
    config.DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    (config.DERIVED_DIR / "subdaily_results.json").write_text(json.dumps(out, indent=2, default=str))
    plot_timelines(floods)
    print(json.dumps({k: v for k, v in out.items() if k != "windows"}, indent=2))
    return out


def plot_timelines(floods: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(floods)
    cols = 3
    rows_n = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows_n, cols, figsize=(12, 1.6 * rows_n), dpi=130, sharey=True)
    for ax, (_, f) in zip(axes.flat, floods.iterrows()):
        days = [(f["date"] + timedelta(days=k)).date() for k in (-1, 0, 1)]
        wide = _half_hourly_mm(imerg.fetch_days(days))
        wettest = wide.max(axis=1) * 2  # mm per hour rate on the wettest cell
        ax.fill_between(wettest.index, wettest.to_numpy(), step="post", color="#2b6cb0", lw=0)
        ax.axvspan(f["date"], f["date"] + pd.Timedelta(days=1), color="#f6c445", alpha=0.25, lw=0)
        ax.set_title(f"{f['date']:%d %b %Y}" + (f"  ({f['time_of_day'][:38]})" if isinstance(f["time_of_day"], str) else ""),
                     fontsize=7, loc="left")
        ax.tick_params(labelsize=6)
        ax.set_xticks([f["date"] + pd.Timedelta(days=k) for k in (-1, 0, 1, 2)])
        ax.set_xticklabels([(f["date"] + pd.Timedelta(days=k)).strftime("%d %b") for k in (-1, 0, 1, 2)])
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    fig.suptitle("Half-hourly satellite rain rate (mm/h, wettest IMERG cell over the peninsula) around each flood; "
                 "yellow = reported flood day", fontsize=9)
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, bbox_inches="tight")
    plt.close(fig)
