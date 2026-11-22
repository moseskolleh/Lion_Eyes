"""Hindcast: would simple rain and tide rules have warned for past floods?

Method (kept deliberately simple and transparent):

* Each flood with a known day ``E`` gets a window ``[E-1, E+1]``. Overnight
  floods are dated by the evening in some reports and by the morning after in
  others, so the neighbouring days count. A rule "hits" a flood if it fires on
  any day in that window. With daily rainfall this tests whether flood days
  stand out as unusually wet (detection), not how much lead time a warning
  would have had; that needs hourly data.
* A "false alarm" is a run of consecutive firing days that touches no flood
  window. Runs, not days, so a three-day wet spell counts once.
* Only rainy-season days (May-November) are scored.
* Thresholds are fixed percentiles of each source's own rainy-season climate,
  not tuned to the floods, so the scores are not flattered by fitting. Using
  percentiles also sidesteps a source's tendency to under-state heavy rain.
* "Skill" per feature is the AUC: the chance that a flood window is wetter
  than a random ordinary window. 0.5 means no information; 1.0 is perfect.

Caveat: the flood catalogue only holds floods that made the news, so some
"false alarms" will be real floods nobody reported. Scores are a lower bound.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from floodwatch import config, events, tides

PERCENTILES = (90, 95, 97.5, 99)


@dataclass
class Score:
    floods: int
    hits: int
    false_alarms: int
    seasons: int

    @property
    def hit_rate(self) -> float:
        return self.hits / self.floods if self.floods else float("nan")

    @property
    def false_alarms_per_season(self) -> float:
        return self.false_alarms / self.seasons if self.seasons else float("nan")


def in_season(index: pd.DatetimeIndex) -> np.ndarray:
    return np.isin(index.month, config.SEASON_MONTHS)


WINDOW_BEFORE, WINDOW_AFTER = 1, 1  # days either side of the reported date


def window_max(series: pd.Series) -> pd.Series:
    """Value for the window [D-1, D+1]: the largest of the three days."""
    shifted = [series.shift(k) for k in range(-WINDOW_AFTER, WINDOW_BEFORE + 1)]
    return pd.concat(shifted, axis=1).max(axis=1, skipna=False)


def _window(e: pd.Timestamp) -> slice:
    return slice(e - pd.Timedelta(days=WINDOW_BEFORE), e + pd.Timedelta(days=WINDOW_AFTER))


def auc(positive: np.ndarray, negative: np.ndarray) -> float:
    """Probability a random positive exceeds a random negative (ties = 0.5)."""
    positive = positive[~np.isnan(positive)]
    negative = negative[~np.isnan(negative)]
    if len(positive) == 0 or len(negative) == 0:
        return float("nan")
    ranks = pd.Series(np.concatenate([positive, negative])).rank().to_numpy()
    n1, n0 = len(positive), len(negative)
    return float((ranks[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def auc_interval(
    positive: np.ndarray, negative: np.ndarray, n: int = 2000, seed: int = 0
) -> tuple[float, float]:
    """90% bootstrap interval for the AUC, resampling the (few) floods."""
    positive = positive[~np.isnan(positive)]
    if len(positive) < 3:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    draws = [auc(rng.choice(positive, size=len(positive)), negative) for _ in range(n)]
    lo, hi = np.percentile(draws, [5, 95])
    return (round(float(lo), 3), round(float(hi), 3))


def flood_windows(index: pd.DatetimeIndex, flood_days: pd.DatetimeIndex) -> pd.Series:
    """Boolean per day: True if the day is in some flood's window."""
    in_window = pd.Series(False, index=index)
    for e in flood_days:
        in_window.loc[_window(e)] = True
    return in_window


def score_rule(fires: pd.Series, flood_days: pd.DatetimeIndex, seasons: int) -> Score:
    """Hits and false-alarm runs for a boolean daily rule."""
    fires = fires.fillna(False).astype(bool)
    hits = sum(bool(fires.loc[_window(e)].any()) for e in flood_days)
    windows = flood_windows(fires.index, flood_days)
    run_id = (fires != fires.shift()).cumsum()
    false_alarms = sum(
        1 for _, run in fires[fires].groupby(run_id[fires]) if not windows.reindex(run.index).any()
    )
    return Score(len(flood_days), hits, false_alarms, seasons)


def tide_daily(tide: pd.Series) -> pd.DataFrame:
    """Highest tide and tidal range (spring/neap) for each day."""
    g = tide.groupby(tide.index.floor("D"))
    return pd.DataFrame({"tide_max": g.max(), "tide_range": g.max() - g.min()})


def tide_check(sea: pd.DataFrame) -> dict:
    """How well the fitted tide reproduces a final year it was not fitted on."""
    sea = sea.dropna(subset=["sea_level_m"])
    cutoff = sea["time"].max() - pd.Timedelta(days=365)
    train, test = sea[sea["time"] < cutoff], sea[sea["time"] >= cutoff]
    pred = tides.predict(tides.fit(train), pd.DatetimeIndex(test["time"]))
    err = test["sea_level_m"].to_numpy() - pred.to_numpy()
    return {
        "fit_hours": int(len(train)),
        "test_hours": int(len(test)),
        "rmse_m": round(float(np.sqrt(np.mean(err**2))), 3),
        "sea_level_std_m": round(float(test["sea_level_m"].std()), 3),
    }


def analyse(
    name: str,
    daily: pd.DataFrame,
    rain_features: list[str],
    catalogue: pd.DataFrame,
) -> dict:
    """Score every rain feature (and tide, if present) against the floods."""
    daily = daily.copy()
    daily.index = pd.DatetimeIndex(daily.index)
    have = daily.dropna(subset=rain_features[:1]).index
    first, last = have[0], have[-1]
    season = daily[in_season(daily.index) & (daily.index >= first) & (daily.index <= last)]
    seasons = len(set(season.index.year))

    dated = catalogue[catalogue["date_confidence"].isin(["exact", "approx_day"])]
    dated = dated[(dated["date"] >= first + pd.Timedelta(days=8)) & (dated["date"] <= last)]
    dated = dated[in_season(pd.DatetimeIndex(dated["date"]))]
    flood_days = pd.DatetimeIndex(dated["date"]).unique().sort_values()

    near = pd.Series(False, index=season.index)
    for e in flood_days:
        near.loc[e - pd.Timedelta(days=3) : e + pd.Timedelta(days=3)] = True
    control = season.index[~near.to_numpy()]

    result: dict = {
        "source": name,
        "period": [str(first.date()), str(last.date())],
        "seasons": seasons,
        "floods_scored": [str(d.date()) for d in flood_days],
        "skill": {},
        "rules": [],
        "tide": {},
        "flood_days": {},
    }
    for feat in rain_features:
        w = window_max(daily[feat])
        pos, neg = w.reindex(flood_days).to_numpy(), w.reindex(control).to_numpy()
        result["skill"][feat] = {
            "auc": round(auc(pos, neg), 3),
            "auc_90pct_interval": auc_interval(pos, neg),
            "median_flood_mm": round(float(np.nanmedian(w.reindex(flood_days))), 1),
            "median_other_mm": round(float(np.nanmedian(w.reindex(control))), 1),
        }
        for pct in PERCENTILES:
            threshold = float(np.nanpercentile(season[feat], pct))
            s = score_rule(season[feat] >= threshold, flood_days, seasons)
            result["rules"].append(
                {
                    "feature": feat,
                    "percentile": pct,
                    "threshold_mm": round(threshold, 1),
                    "hits": s.hits,
                    "floods": s.floods,
                    "false_alarms_per_season": round(s.false_alarms_per_season, 1),
                }
            )
        # Each flood's value as a percentile of ordinary rainy-season days.
        ref = np.sort(w.reindex(control).dropna().to_numpy())
        for d in flood_days:
            v = w.get(d, np.nan)
            pct = float(np.searchsorted(ref, v, side="right") / len(ref) * 100) if pd.notna(v) else None
            result["flood_days"].setdefault(str(d.date()), {})[feat] = {
                "mm": None if pd.isna(v) else round(float(v), 1),
                "percentile": None if pct is None else round(pct, 1),
            }

    if "tide_range" in daily:
        coastal = pd.DatetimeIndex(dated.loc[dated["coastal"], "date"]).unique()
        inland = pd.DatetimeIndex(dated.loc[~dated["coastal"], "date"]).unique()
        for feat in ("tide_max", "tide_range"):
            w = window_max(daily[feat])
            neg = w.reindex(control).to_numpy()
            result["tide"][feat] = {
                "auc_all": round(auc(w.reindex(flood_days).to_numpy(), neg), 3),
                "auc_coastal": round(auc(w.reindex(coastal).to_numpy(), neg), 3),
                "auc_inland": round(auc(w.reindex(inland).to_numpy(), neg), 3),
                "n_coastal": len(coastal),
                "n_inland": len(inland),
            }
    return result


def run(first_year: int = config.FIRST_YEAR) -> dict:
    from floodwatch.sources import chirps

    catalogue = events.load_catalogue()
    sea = pd.read_csv(config.RAW_DIR / "tables" / "sea_level.csv.gz", parse_dates=["time"])
    hours = pd.date_range(f"{config.FIRST_YEAR}-01-01", pd.Timestamp.today().normalize(), freq="h")
    tide = tides.predict(tides.fit(sea), hours)

    cells = chirps.fetch(first_year, pd.Timestamp.today().year)
    daily = chirps.daily_features(cells).join(tide_daily(tide), how="left")
    config.DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    daily.round(3).to_csv(config.DERIVED_DIR / "daily_features_chirps.csv")

    results = {
        "tide_fit_check": tide_check(sea),
        "chirps": analyse(
            "CHIRPS v3 daily (satellite + gauges, IMERG-timed)",
            daily,
            ["day_max", "day_mean", "prev_3d", "prev_7d", "day_plus_prev_3d"],
            catalogue,
        ),
    }
    (config.DERIVED_DIR / "hindcast_results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    return results
