"""Backtest of the daily Outlook on archived ECMWF forecasts (2024-2026).

The live Outlook turns ECMWF's 51-member ensemble into a level (LOW, ELEVATED,
HIGH) for today, tomorrow and the day after. This replays it on the 00 UTC
runs of past days, with the same rules (`outlook.day_levels`), and asks:

1. Before the floods in the history, did it raise ELEVATED or HIGH?
2. How often does it raise them on ordinary rainy-season days?
3. How well does the forecast rain match the satellite (CHIRPS) rain?

Differences from the live Outlook, both forced by data availability:
- Observed rain for the wet-ground rule is CHIRPS (peninsula mean), not IMERG,
  because CHIRPS covers the whole period with one consistent product.
- ECMWF's open-data ensemble is on the live 0.25 deg grid only from 2024;
  earlier runs are on a coarser grid, so the backtest starts with the 2024 season.

The random sample of issue days is drawn once and frozen in SAMPLE_CSV, so
re-running (or adding floods) does not redraw it or re-download its forecasts.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from floodwatch import config, outlook, subdaily
from floodwatch.hindcast import auc, auc_interval
from floodwatch.sources import ecmwf, imerg

FIRST_DAY = date(2024, 5, 1)
FETCH_WORKERS = 3  # bulk downloads: fewer parallel requests, so the archive does not throttle us
SEASON_DAYS = 214  # 1 May - 30 Nov
ISSUE_HOUR = 9.5  # the daily job runs at 09:23 UTC; Freetown is on UTC
LEVELS = ["LOW", "ELEVATED", "HIGH"]
SAMPLE_CSV = config.DERIVED_DIR / "outlook_backtest_sample.csv"
DAYS_CSV = config.DERIVED_DIR / "outlook_backtest_days.csv"
RESULTS_JSON = config.DERIVED_DIR / "outlook_backtest.json"
EVENING_DAYS_CSV = config.DERIVED_DIR / "outlook_backtest_evening_days.csv"
EVENING_JSON = config.DERIVED_DIR / "outlook_backtest_evening.json"
EVENING_HOUR = 20.8  # the evening job runs at 20:47 UTC


def observed() -> pd.Series:
    """CHIRPS peninsula-mean daily rain (mm), indexed by date."""
    d = pd.read_csv(config.DERIVED_DIR / "daily_features_chirps.csv", parse_dates=["date"])
    return d.set_index("date")["day_mean"]


def random_sample(last_issue: date, n: int = 120, seed: int = 11) -> list[date]:
    if SAMPLE_CSV.exists():
        return [d.date() for d in pd.read_csv(SAMPLE_CSV, parse_dates=["issue"])["issue"]]
    days = pd.date_range(FIRST_DAY, last_issue)
    days = days[days.month.isin(config.SEASON_MONTHS)]
    rng = np.random.default_rng(seed)
    picked = sorted(rng.choice(days, size=n, replace=False))
    pd.DataFrame({"issue": [pd.Timestamp(d).date() for d in picked]}).to_csv(SAMPLE_CSV, index=False)
    return [pd.Timestamp(d).date() for d in picked]


def replay(issue: date, obs: pd.Series) -> list[dict]:
    """The Outlook as it would have been issued on the morning of `issue`."""
    members = ecmwf.daily_rain(ecmwf.fetch_run(issue, 0, workers=FETCH_WORKERS))
    before = [float(obs.get(pd.Timestamp(issue - timedelta(days=k)), np.nan)) for k in (3, 2, 1)]
    rows = outlook.day_levels(members, issue, before)
    for k, r in enumerate(rows, 1):
        r.update(issue=issue, lead_day=k, observed_mm=float(obs.get(pd.Timestamp(r["day"]), np.nan)),
                 wet_mm=outlook._scaled(r["day"].month)[0])
    return rows


def _rate(x: pd.Series) -> float:
    return round(float(x.mean()), 3)


def score(days: pd.DataFrame, sample: list[date], floods: list[date],
          reported: dict[str, tuple[str, str]] | None = None) -> dict:
    """`reported`: flood date -> (reported time, note), as in `subdaily.REPORTED_TIMES`."""
    reported = subdaily.REPORTED_TIMES if reported is None else reported
    days = days.copy()
    days["lvl"] = days["level"].map(LEVELS.index)
    days["forecast_wet"] = (days["p_wet"] >= outlook.LIKELY) | (days["p_very_wet"] >= outlook.LIKELY)
    days["saturated"] = days["prior_3d_mm"] >= outlook.SATURATED_3D_MM
    at = days.set_index(["issue", "lead_day"])

    def window(issue: date, leads: tuple[int, ...], col: str, how: str = "max") -> float:
        vals = [at.loc[(issue, k), col] for k in leads if (issue, k) in at.index]
        return float(getattr(np, how)(vals)) if vals else np.nan

    # The public sees one headline per morning: the highest level for today or tomorrow.
    rnd = pd.DataFrame({
        "issue": sample,
        "lvl": [window(i, (1, 2), "lvl") for i in sample],
        "p_wet": [window(i, (1, 2), "p_wet") for i in sample],
        "prior_obs": [at.loc[(i, 1), "prior_3d_mm"] for i in sample],
        "forecast_wet": [window(i, (1, 2), "forecast_wet") for i in sample],
        "saturated": [window(i, (1, 2), "saturated") for i in sample],
    })
    alerts = rnd[rnd["lvl"] >= 1]
    ordinary = {
        "issue_days": len(rnd),
        "elevated_or_high": _rate(rnd["lvl"] >= 1),
        "high": _rate(rnd["lvl"] >= 2),
        "alert_days_per_season": round(float((rnd["lvl"] >= 1).mean()) * SEASON_DAYS),
        "high_days_per_season": round(float((rnd["lvl"] >= 2).mean()) * SEASON_DAYS),
        "alerts_from_forecast": int(alerts["forecast_wet"].astype(bool).sum()),
        "alerts_from_wet_ground_only": int((~alerts["forecast_wet"].astype(bool)).sum()),
    }

    per_flood = []
    for d in floods:
        row = {"flood": d.isoformat()}
        # Same morning: today's level. Day before: today (D-1) or tomorrow (D).
        # Two days before: tomorrow (D-1) or the day after (D).
        for name, issue, leads in (("same_morning", d, (1,)), ("day_before", d - timedelta(days=1), (1, 2)),
                                   ("two_days_before", d - timedelta(days=2), (2, 3))):
            lvl = window(issue, leads, "lvl")
            row[name] = LEVELS[int(lvl)] if not np.isnan(lvl) else None
            row[name + "_p_wet"] = window(issue, leads, "p_wet")
        # In time: the latest Outlook issued before the flood. A flood reported after the
        # morning issue counts the same-morning Outlook; one before it (or at an unknown
        # time) only the day-before Outlook.
        t = reported.get(d.isoformat(), (None,))[0]
        when = pd.Timestamp(t) if t else None
        same_ok = when is not None and when >= pd.Timestamp(d) + pd.Timedelta(hours=ISSUE_HOUR)
        row["reported_time"] = t
        row["in_time_from"] = "same morning" if same_ok else "day before"
        row["in_time"] = row["same_morning"] if same_ok else row["day_before"]
        row["prior_obs_day_before"] = window(d - timedelta(days=1), (1,), "prior_3d_mm")
        row["forecast_wet_day_before"] = bool(window(d - timedelta(days=1), (1, 2), "forecast_wet"))
        row["observed_mm_d_minus_1_to_d"] = round(window(d - timedelta(days=1), (1, 2), "observed_mm", "nanmax"), 1)
        per_flood.append(row)
    pf = pd.DataFrame(per_flood)

    def hits(col: str, minimum: str) -> int:
        return int(pf[col].map(lambda v: isinstance(v, str) and LEVELS.index(v) >= LEVELS.index(minimum)).sum())

    flood_summary = {
        lead: {"elevated_or_high": hits(lead, "ELEVATED"), "high": hits(lead, "HIGH"),
               "of": int(pf[lead].map(lambda v: isinstance(v, str)).sum())}
        for lead in ("in_time", "same_morning", "day_before", "two_days_before")
    }

    # Continuous scores, floods (issued the day before) vs ordinary issue days.
    fl_p = pf["day_before_p_wet"].to_numpy(float)
    fl_prior = pf["prior_obs_day_before"].to_numpy(float)
    separation = {
        "forecast_p_wet": {"auc": round(auc(fl_p, rnd["p_wet"].to_numpy(float)), 2),
                           "auc_90pct": auc_interval(fl_p, rnd["p_wet"].to_numpy(float))},
        "observed_rain_previous_3_days": {"auc": round(auc(fl_prior, rnd["prior_obs"].to_numpy(float)), 2),
                                          "auc_90pct": auc_interval(fl_prior, rnd["prior_obs"].to_numpy(float))},
    }

    # Forecast rain vs satellite rain on the random issue days.
    skill = {}
    s = days[days["issue"].isin(sample)].dropna(subset=["observed_mm"])
    for k in (1, 2, 3):
        x = s[s["lead_day"] == k]
        wet_obs = x["observed_mm"] >= x["wet_mm"]
        said_wet = x["p_wet"] >= outlook.LIKELY
        skill[f"day_{k}"] = {
            "n": len(x),
            "rank_correlation_median_vs_observed": round(float(x["median_mm"].corr(x["observed_mm"], method="spearman")), 2),
            "observed_wet_days": int(wet_obs.sum()),
            "wet_days_forecast": int((wet_obs & said_wet).sum()),
            "forecast_wet_days_that_were_wet": f"{int((wet_obs & said_wet).sum())} of {int(said_wet.sum())}",
            "auc_p_wet_for_wet_days": round(auc(x.loc[wet_obs, "p_wet"].to_numpy(float),
                                                x.loc[~wet_obs, "p_wet"].to_numpy(float)), 2),
            "median_forecast_mm_on_wet_days": round(float(x.loc[wet_obs, "median_mm"].median()), 1),
            "median_observed_mm_on_wet_days": round(float(x.loc[wet_obs, "observed_mm"].median()), 1),
        }

    return {"period": f"{FIRST_DAY} to {max(days['day'])}", "ordinary_days": ordinary,
            "floods": flood_summary, "per_flood": per_flood, "separation": separation, "forecast_skill": skill}


def run(n_random: int = 120) -> dict:
    obs = observed()
    last_obs = obs.index.max().date()
    sample = random_sample(last_obs - timedelta(days=2), n_random)
    fl = subdaily.flood_dates()
    floods = sorted(d.date() for d in fl["date"] if FIRST_DAY + timedelta(days=2) <= d.date() <= last_obs)
    issues = sorted(set(sample) | {d - timedelta(days=k) for d in floods for k in (0, 1, 2)})
    rows = []
    for i, issue in enumerate(issues, 1):
        try:
            rows += replay(issue, obs)
        except Exception as exc:  # noqa: BLE001 - a missing run should not stop the backtest
            print(f"{issue}: skipped ({exc})")
            continue
        if i % 10 == 0 or i == len(issues):
            print(f"{i}/{len(issues)} runs", flush=True)
    days = pd.DataFrame(rows)
    days.to_csv(DAYS_CSV, index=False)
    results = score(days, [d for d in sample if d in set(days["issue"])], floods)
    RESULTS_JSON.write_text(json.dumps(results, indent=2, default=str))
    print(json.dumps({k: v for k, v in results.items() if k != "per_flood"}, indent=2, default=str))
    print(pd.DataFrame(results["per_flood"]).to_string(index=False))
    return results


# --- Evening issue -----------------------------------------------------------
# The evening Outlook uses the 12 UTC run: periods run noon to noon, the first
# covering tonight. Wet ground before it = CHIRPS for the 2 previous days plus
# IMERG for 00-12 UTC of the issue day (CHIRPS has no part-day values).


def replay_evening(issue: date, obs: pd.Series) -> list[dict]:
    members = ecmwf.daily_rain(ecmwf.fetch_run(issue, 12, workers=FETCH_WORKERS))
    before = [float(obs.get(pd.Timestamp(issue - timedelta(days=k)), np.nan)) for k in (2, 1)]
    before.append(imerg.total_until(issue, 12)["mean_mm"])
    rows = outlook.day_levels(members, issue, before)
    for k, r in enumerate(rows, 1):
        r.update(issue=issue, lead_day=k)
    return rows


def _latest_issue(flood: date, when: pd.Timestamp | None) -> tuple[str, date]:
    """The last Outlook (morning ~09:30 or evening ~20:50) issued before the flood.
    Unknown time: the evening before (an issue before any hour of the flood day)."""
    day = pd.Timestamp(flood)
    if when is not None and when >= day + pd.Timedelta(hours=EVENING_HOUR):
        return "evening", flood
    if when is not None and when >= day + pd.Timedelta(hours=ISSUE_HOUR):
        return "morning", flood
    return "evening", flood - timedelta(days=1)


def run_evening(reported: dict[str, tuple[str, str]] | None = None) -> dict:
    """Evening issues before each flood and on the frozen random sample of days.

    Compares 'in time' with and without the evening issue, and how often the
    evening issue raises alerts on ordinary days. Needs the morning backtest
    (`run`) first, for the morning levels.
    """
    reported = subdaily.REPORTED_TIMES if reported is None else reported
    obs = observed()
    morning = pd.read_csv(DAYS_CSV, parse_dates=["issue"])
    morning["issue"] = morning["issue"].dt.date
    m_at = morning.assign(lvl=morning["level"].map(LEVELS.index)).set_index(["issue", "lead_day"])["lvl"]
    last_obs = obs.index.max().date()
    floods = sorted(d.date() for d in subdaily.flood_dates()["date"]
                    if FIRST_DAY + timedelta(days=2) <= d.date() <= last_obs)
    sample = random_sample(last_obs - timedelta(days=2))
    issues = sorted({d - timedelta(days=1) for d in floods} | set(floods) | set(sample))
    rows = []
    for i, issue in enumerate(issues, 1):
        try:
            rows += replay_evening(issue, obs)
        except Exception as exc:  # noqa: BLE001
            print(f"evening {issue}: skipped ({exc})")
        if i % 10 == 0 or i == len(issues):
            print(f"{i}/{len(issues)} evening runs", flush=True)
    days = pd.DataFrame(rows)
    days.to_csv(EVENING_DAYS_CSV, index=False)
    e_at = days.assign(lvl=days["level"].map(LEVELS.index)).set_index(["issue", "lead_day"])["lvl"]

    def lvl(at: pd.Series, issue: date, leads: tuple[int, ...]) -> float:
        vals = [at[(issue, k)] for k in leads if (issue, k) in at.index]
        return float(max(vals)) if vals else np.nan

    def name(v: float) -> str | None:
        return None if np.isnan(v) else LEVELS[int(v)]

    per_flood = []
    for d in floods:
        t = reported.get(d.isoformat(), (None,))[0]
        when = pd.Timestamp(t) if t else None
        m_same = when is not None and when >= pd.Timestamp(d) + pd.Timedelta(hours=ISSUE_HOUR)
        morning_only = lvl(m_at, d, (1,)) if m_same else lvl(m_at, d - timedelta(days=1), (1, 2))
        edition, issue = _latest_issue(d, when)
        if edition == "morning":
            latest, previous = lvl(m_at, d, (1,)), lvl(e_at, d - timedelta(days=1), (1, 2))
        else:
            # Evening issue: tonight's period, plus the next one when the flood is the day after.
            latest = lvl(e_at, issue, (1,) if issue == d else (1, 2))
            previous = lvl(m_at, issue, (1, 2))
        per_flood.append({"flood": d.isoformat(), "reported_time": t, "morning_only_in_time": name(morning_only),
                          "latest_issue": f"{edition} {issue}", "latest_in_time": name(latest),
                          "best_of_last_two": name(np.nanmax([latest, previous]))})
    pf = pd.DataFrame(per_flood)

    def count(col: str, minimum: str) -> int:
        return int(pf[col].map(lambda v: isinstance(v, str) and LEVELS.index(v) >= LEVELS.index(minimum)).sum())

    s_ok = [i for i in sample if (i, 1) in e_at.index and (i, 1) in m_at.index]
    ev = np.array([lvl(e_at, i, (1, 2)) for i in s_ok])
    mo = np.array([lvl(m_at, i, (1, 2)) for i in s_ok])
    either = np.maximum(ev, mo)
    ordinary = {
        "issue_days": len(s_ok),
        "evening_elevated_or_high": round(float((ev >= 1).mean()), 3),
        "evening_high": round(float((ev >= 2).mean()), 3),
        "morning_elevated_or_high": round(float((mo >= 1).mean()), 3),
        "morning_high": round(float((mo >= 2).mean()), 3),
        "days_with_any_elevated_or_high_per_season": round(float((either >= 1).mean()) * SEASON_DAYS),
        "days_with_any_high_per_season": round(float((either >= 2).mean()) * SEASON_DAYS),
        "morning_only_high_days_per_season": round(float((mo >= 2).mean()) * SEASON_DAYS),
        "morning_only_elevated_or_high_days_per_season": round(float((mo >= 1).mean()) * SEASON_DAYS),
    }
    results = {
        "floods": len(pf),
        "in_time": {col: {"elevated_or_high": count(col, "ELEVATED"), "high": count(col, "HIGH")}
                    for col in ("morning_only_in_time", "latest_in_time", "best_of_last_two")},
        "ordinary_days": ordinary,
        "per_flood": per_flood,
    }
    EVENING_JSON.write_text(json.dumps(results, indent=2, default=str))
    print(pf.to_string(index=False))
    print(json.dumps({k: v for k, v in results.items() if k != "per_flood"}, indent=2))
    return results
