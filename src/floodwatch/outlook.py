"""Daily flood Outlook for the next three days (v0).

Inputs, all available remotely every day:
* ECMWF ensemble rain forecast for days 1-3 (50 members, peninsula average);
* observed rain in the previous 3 days (NASA IMERG near-real-time);
* predicted tide (for low ground at stream mouths and the shore).

Levels per day:
* HIGH      - a very wet day is likely, or a wet day is likely on already
              saturated ground;
* ELEVATED  - a wet day is likely, or the ground is already saturated;
* LOW       - neither.

THE RAIN THRESHOLDS ARE PROVISIONAL. They are set from the CHIRPS hindcast
(flood days had ~60-75 mm peninsula-average rain; the wettest 5% of rainy-
season days exceed ~58 mm) but the forecast model has its own rain climate.
Every run is archived (data/raw/ecmwf) so that after one rainy season the
thresholds can be recalibrated as percentiles of the model's own forecasts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from floodwatch import config, tides
from floodwatch.sources import ecmwf, imerg

WET_DAY_MM = 30.0  # peninsula-average rain in a day: "wet"
VERY_WET_DAY_MM = 50.0  # "very wet"
SATURATED_3D_MM = 100.0  # rain in the previous 3 days: ground saturated
LIKELY = 0.30  # share of ensemble members needed to call something "likely"
# Early- and late-season floods have happened with less rain (dry-season
# rubbish in drains, loose slopes): lower thresholds then. Weak evidence (4 events).
TRANSITION_FACTOR = {5: 0.6, 6: 0.8, 10: 0.8, 11: 0.8}
HIGH_TIDE_M = 1.1  # a spring-tide high water at Freetown (M2 ~0.9 m + S2 ~0.3 m)
MIN_PEOPLE = 500  # a zone is named in the bulletin if at least this many live on its risky ground


@dataclass
class DayOutlook:
    day: date
    p_wet: float
    p_very_wet: float
    median_mm: float
    prior_3d_mm: float
    level: str
    high_tides: list[str]


def classify(p_wet: float, p_very_wet: float, prior_3d_mm: float) -> str:
    saturated = prior_3d_mm >= SATURATED_3D_MM
    if p_very_wet >= LIKELY or (saturated and p_wet >= LIKELY):
        return "HIGH"
    if p_wet >= LIKELY or saturated:
        return "ELEVATED"
    return "LOW"


def _scaled(month: int) -> tuple[float, float]:
    f = TRANSITION_FACTOR.get(month, 1.0)
    return WET_DAY_MM * f, VERY_WET_DAY_MM * f


def _high_tides(tide: pd.Series, day: date) -> list[str]:
    t = tide[(tide.index >= pd.Timestamp(day)) & (tide.index < pd.Timestamp(day) + pd.Timedelta(days=1))]
    peaks = t[(t.shift(1) < t) & (t.shift(-1) <= t) & (t >= HIGH_TIDE_M)]
    return [f"{ts:%H:%M} ({h:.1f} m)" for ts, h in peaks.items()]


def day_levels(members: pd.DataFrame, first_day: date, observed: list[float]) -> list[dict]:
    """Levels for forecast days 1-3 of one ensemble run.

    `members` comes from `ecmwf.daily_rain`; `observed` is the peninsula-mean
    rain on the days just before `first_day`, oldest first (may be empty).
    Shared by the live Outlook and the backtest, so both apply the same rules.
    """
    median_by_day = members.groupby("day")["mean_mm"].median()
    # Rain day by day, oldest first: the observed days, then the forecast medians.
    sequence = list(observed) + [float(median_by_day.loc[k]) for k in (1, 2, 3)]
    out = []
    for k in (1, 2, 3):
        valid = first_day + timedelta(days=k - 1)
        rain = members.loc[members["day"] == k, "mean_mm"]
        wet, very_wet = _scaled(valid.month)
        here = len(observed) + k - 1  # position of this day in `sequence`
        prior = sum(sequence[max(0, here - 3) : here])  # the 3 days before it
        p_wet, p_very = float((rain >= wet).mean()), float((rain >= very_wet).mean())
        out.append({"day": valid, "p_wet": round(p_wet, 2), "p_very_wet": round(p_very, 2),
                    "median_mm": round(float(rain.median()), 1), "prior_3d_mm": round(prior, 1),
                    "level": classify(p_wet, p_very, prior)})
    return out


def build(run: tuple[date, int] | None = None, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    run = run or ecmwf.latest_run()
    members = ecmwf.daily_rain(ecmwf.fetch_run(*run))
    run_start = pd.Timestamp(run[0]) + pd.Timedelta(hours=run[1])

    # Observed rain needs a NASA Earthdata token; without one (or if NASA is
    # down) the Outlook still runs on the forecast and says wetness is unknown.
    observed = []
    for k in (3, 2, 1):
        try:
            observed.append(imerg.daily_total(today - timedelta(days=k)))
        except Exception as exc:  # noqa: BLE001 - any failure here is non-fatal
            print(f"observed rain for {today - timedelta(days=k)} unavailable: {exc}")
    prior_obs = sum(o["mean_mm"] for o in observed)

    tide = tides.predict(tides.model(), pd.date_range(pd.Timestamp(today), periods=4 * 24 * 6, freq="10min"))

    days = [DayOutlook(**d, high_tides=_high_tides(tide, d["day"]))
            for d in day_levels(members, run_start.date(), [o["mean_mm"] for o in observed])]

    zones = pd.read_csv(config.DERIVED_DIR / "zones.csv")
    city = zones[(zones["zone_id"] > 0) & zones["in_city"]]
    # With exposure counts (`floodwatch exposure`), pick zones by how many
    # people live on the risky ground; otherwise fall back to land area.
    has_people = "people_low_ground" in city
    if has_people:
        low = city[city["people_low_ground"] >= MIN_PEOPLE].sort_values("people_low_ground", ascending=False)
        steep = city[city["people_steep"] >= MIN_PEOPLE].sort_values("people_steep", ascending=False)
    else:
        low = city[city["low_ground_km2"] >= 0.1].sort_values("low_ground_km2", ascending=False)
        steep = city[city["steep_share"] >= 0.15].sort_values("area_km2", ascending=False)
    people_low = int(low["people_low_ground"].sum()) if has_people else None
    people_steep = int(steep["people_steep"].sum()) if has_people else None
    low, steep = low["name"].tolist(), steep["name"].tolist()

    out = {
        "issued": today.isoformat(),
        "forecast_run": f"{run[0]:%Y-%m-%d} {run[1]:02d}:00 UTC",
        "observed_rain_last_3_days_mm": round(prior_obs, 1) if observed else None,
        "observed_days": observed,
        "days": [d.__dict__ | {"day": d.day.isoformat()} for d in days],
        "low_ground_zones": low,
        "steep_zones": steep,
        "people_low_ground": people_low,
        "people_steep": people_steep,
        "thresholds": {"wet_mm": WET_DAY_MM, "very_wet_mm": VERY_WET_DAY_MM,
                       "saturated_3d_mm": SATURATED_3D_MM, "likely": LIKELY, "provisional": True},
    }
    folder = config.DATA_DIR / "outlook"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{today.isoformat()}.json").write_text(json.dumps(out, indent=2, default=str))
    text = to_text(out)
    (folder / f"{today.isoformat()}.md").write_text(text)
    print(text)
    return out


def to_text(o: dict) -> str:
    lines = [
        f"# Freetown flood outlook, issued {o['issued']}",
        "",
        f"Forecast: ECMWF ensemble run {o['forecast_run']}. Rain in the last 3 days (satellite): "
        + (f"{o['observed_rain_last_3_days_mm']:.0f} mm"
           + ("" if len(o["observed_days"]) == 3 else f" ({len(o['observed_days'])} of 3 days available)")
           if o["observed_rain_last_3_days_mm"] is not None else "not available, so ground wetness is unknown")
        + ".",
        "",
        "| Day | Level | Chance of a wet day | Chance of a very wet day | Most likely rain | Ground wetness (prior 3 days) | High tides |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in o["days"]:
        tides_text = ", ".join(d["high_tides"]) or "-"
        lines.append(
            f"| {pd.Timestamp(d['day']):%a %d %b} | **{d['level']}** | {d['p_wet']:.0%} | {d['p_very_wet']:.0%} | "
            f"{d['median_mm']:.0f} mm | {d['prior_3d_mm']:.0f} mm | {tides_text} |"
        )
    worst = max(o["days"], key=lambda d: ["LOW", "ELEVATED", "HIGH"].index(d["level"]))
    lines += ["", "**What to do**", ""]
    if worst["level"] == "LOW":
        lines.append("No action needed. Normal monitoring.")
    else:
        lines.append(
            f"- **Low ground at stream mouths and the shore** ({', '.join(o['low_ground_zones'][:8])})"
            + (f", about {o['people_low_ground']:,} people" if o.get("people_low_ground") else "")
            + ": be ready to move people from the lowest homes, especially around the high tides listed."
        )
        lines.append(
            f"- **Steep hillsides** ({', '.join(o['steep_zones'][:6])})"
            + (f", about {o['people_steep']:,} people on steep slopes" if o.get("people_steep") else "")
            + ": watch for runoff, cracks and leaning walls; after several wet days, landslide risk rises."
        )
    lines += ["", "*v0: rain thresholds are provisional until calibrated against a season of archived forecasts.*"]
    return "\n".join(lines) + "\n"
