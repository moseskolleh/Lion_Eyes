"""Flood Outlook for the next three days (v0), issued morning and evening.

Inputs, all available remotely every day:
* ECMWF ensemble rain forecast (50 members, peninsula average). The morning
  issue uses the 00 UTC run (published ~07:40 UTC): periods are calendar days.
  The evening issue uses the 12 UTC run (published ~19:40 UTC): periods run
  noon to noon, so the first one covers tonight with a fresh forecast. Most
  Freetown floods happen at night or before dawn (see the backtest).
* observed rain before the first period (NASA IMERG near-real-time): the 3
  previous days for the morning issue; the 2 previous days plus this morning
  for the evening issue;
* predicted tide (for low ground at stream mouths and the shore).

Levels per period:
* HIGH (act)        - a very wet period is likely, or a wet period is likely
                      on already saturated ground;
* ELEVATED (watch)  - a wet period is likely, or the ground is saturated;
* LOW               - neither.

THE RAIN THRESHOLDS ARE PROVISIONAL. They come from the CHIRPS hindcast; the
backtest (`floodwatch backtest`) shows how often each level came before
floods and on ordinary days. Every forecast run is archived in
data/archive/ecmwf for recalibration.
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
LEVEL_WORDS = {"HIGH": "HIGH (act)", "ELEVATED": "ELEVATED (watch)", "LOW": "LOW"}
EVENING_FROM_HOUR = 15  # an Outlook built after 15:00 UTC is the evening issue


@dataclass
class DayOutlook:
    day: date
    p_wet: float
    p_very_wet: float
    median_mm: float
    prior_3d_mm: float
    level: str
    start: str
    end: str
    label: str
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


def _high_tides(tide: pd.Series, start: date | pd.Timestamp) -> list[str]:
    """High waters above HIGH_TIDE_M in the 24 hours from `start`."""
    t = tide[(tide.index >= pd.Timestamp(start)) & (tide.index < pd.Timestamp(start) + pd.Timedelta(days=1))]
    peaks = t[(t.shift(1) < t) & (t.shift(-1) <= t) & (t >= HIGH_TIDE_M)]
    # A noon-to-noon period crosses midnight, so name the day.
    fmt = "%H:%M" if pd.Timestamp(start).hour == 0 else "%a %H:%M"
    return [f"{ts:{fmt}} ({h:.1f} m)" for ts, h in peaks.items()]


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


def _observed_before(start: pd.Timestamp) -> tuple[list[dict], str]:
    """Observed peninsula rain before the first forecast period, and a label.

    00 UTC start: the 3 previous days. 12 UTC start: the 2 previous days plus
    the morning (00-12 UTC) of the start day. Needs a NASA Earthdata token;
    without one (or if NASA is down) the Outlook still runs on the forecast
    and says wetness is unknown.
    """
    day = start.date()
    if start.hour == 12:
        jobs, label = [(day - timedelta(days=2), None), (day - timedelta(days=1), None), (day, 12)], "the last 2½ days"
    else:
        jobs, label = [(day - timedelta(days=k), None) for k in (3, 2, 1)], "the last 3 days"
    observed = []
    for d, until in jobs:
        try:
            observed.append(imerg.daily_total(d) if until is None else imerg.total_until(d, until))
        except Exception as exc:  # noqa: BLE001 - any failure here is non-fatal
            print(f"observed rain for {d} unavailable: {exc}")
    return observed, label


def _period_label(start: pd.Timestamp, end: pd.Timestamp, first: bool) -> str:
    if start.hour == 0:
        return f"{start:%a %d %b}"
    if first:
        return f"Tonight to noon {end:%a %d %b}"
    return f"Noon {start:%a %d} to noon {end:%a %d %b}"


def build(run: tuple[date, int] | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.date()
    edition = "evening" if now.hour >= EVENING_FROM_HOUR else "morning"
    run = run or ecmwf.latest_run(now)
    members = ecmwf.daily_rain(ecmwf.fetch_run(*run))
    run_start = pd.Timestamp(run[0]) + pd.Timedelta(hours=run[1])

    observed, observed_label = _observed_before(run_start)
    prior_obs = sum(o["mean_mm"] for o in observed)

    tide = tides.predict(tides.model(), pd.date_range(run_start.floor("D"), periods=5 * 24 * 6, freq="10min"))

    days = []
    for k, d in enumerate(day_levels(members, run_start.date(), [o["mean_mm"] for o in observed])):
        start = run_start + pd.Timedelta(days=k)
        end = start + pd.Timedelta(days=1)
        days.append(DayOutlook(**d, start=start.isoformat(), end=end.isoformat(),
                               label=_period_label(start, end, k == 0), high_tides=_high_tides(tide, start)))

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
        "edition": edition,
        "issued_at": now.strftime("%Y-%m-%dT%H:%MZ"),
        "forecast_run": f"{run[0]:%Y-%m-%d} {run[1]:02d}:00 UTC",
        "observed_rain_last_3_days_mm": round(prior_obs, 1) if observed else None,
        "observed_period": observed_label,
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
    stem = today.isoformat() + ("-evening" if edition == "evening" else "")
    (folder / f"{stem}.json").write_text(json.dumps(out, indent=2, default=str))
    text = to_text(out)
    (folder / f"{stem}.md").write_text(text)
    print(text)
    return out


def level_rates() -> dict | None:
    """How often each level came up in the backtest (both issues a day), if it has been run."""
    try:
        r = json.loads((config.DERIVED_DIR / "outlook_backtest_evening.json").read_text())
        od, fl = r["ordinary_days"], r["in_time"]["best_of_last_two"]
        season = 214  # 1 May - 30 Nov
        return {"high_pct": round(100 * od["days_with_any_high_per_season"] / season),
                "elevated_pct": round(100 * od["days_with_any_elevated_or_high_per_season"] / season),
                "floods_high": fl["high"], "floods_of": r["floods"]}
    except (OSError, ValueError, KeyError):
        return None


def level_meaning(bold: tuple[str, str] = ("**", "**")) -> str:
    """One sentence per level on what it means and how often it comes up."""
    b0, b1 = bold
    r = level_rates()
    if r:
        high = (f"the rarer, stronger signal. Replaying 2024-2026 forecasts, it came up on about {r['high_pct']}% "
                f"of rainy-season days and in time before {r['floods_high']} of {r['floods_of']} floods")
        elevated = f"common, on about {r['elevated_pct']}% of rainy-season days (counting HIGH)"
    else:
        high, elevated = "the rarer, stronger signal", "common"
    return (f"{b0}HIGH = act{b1}: {high}. {b0}ELEVATED = watch{b1}: {elevated}; most such days pass "
            "without flooding. LOW = normal. Read the morning and evening issues together.")


def to_text(o: dict) -> str:
    evening = o.get("edition") == "evening"
    n_obs = len(o["observed_days"])
    expected = 3
    wet = o["observed_rain_last_3_days_mm"]
    period = o.get("observed_period", "the last 3 days")
    lines = [
        f"# Freetown flood outlook, {'evening' if evening else 'morning'} of {o['issued']}"
        if "edition" in o else f"# Freetown flood outlook, issued {o['issued']}",
        "",
        f"Forecast: ECMWF ensemble run {o['forecast_run']}. Rain in {period} (satellite): "
        + (f"{wet:.0f} mm" + ("" if n_obs == expected else f" ({n_obs} of {expected} parts available)")
           if wet is not None else "not available, so ground wetness is unknown")
        + ".",
    ]
    if evening and o["days"] and pd.Timestamp(o["days"][0].get("start", o["days"][0]["day"])).hour == 12:
        lines += ["", "Periods run noon to noon, Freetown time (UTC). The first began at noon today, so it covers "
                      "this afternoon's rain as well as tonight."]
    first_col = "Period" if evening else "Day"
    lines += [
        "",
        f"| {first_col} | Level | Chance of a wet {first_col.lower()} | Chance of a very wet {first_col.lower()} | "
        "Most likely rain | Ground wetness (rain in the days before) | High tides |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in o["days"]:
        tides_text = ", ".join(d["high_tides"]) or "-"
        label = d.get("label") or f"{pd.Timestamp(d['day']):%a %d %b}"
        lines.append(
            f"| {label} | **{LEVEL_WORDS.get(d['level'], d['level'])}** | {d['p_wet']:.0%} | {d['p_very_wet']:.0%} | "
            f"{d['median_mm']:.0f} mm | {d['prior_3d_mm']:.0f} mm | {tides_text} |"
        )
    worst = max(o["days"], key=lambda d: ["LOW", "ELEVATED", "HIGH"].index(d["level"]))
    next_issue = "tomorrow morning's" if evening else "this evening's"
    lines += ["", "**What to do**", ""]
    if worst["level"] == "LOW":
        lines.append("No action needed. Normal monitoring.")
    elif worst["level"] == "ELEVATED":
        lines.append(
            "**Watch.** No action yet: most days at this level pass without flooding. Clear drains and gutters near "
            f"low ground ({', '.join(o['low_ground_zones'][:5])}), watch the sky, and check {next_issue} update."
        )
    else:
        lines.append("**Act.**")
        lines.append("")
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
    lines += ["", "**What the levels mean.** " + level_meaning(),
              "", "*v0: thresholds are provisional. Issued twice a day, around 09:30 and 21:00 Freetown time.*"]
    return "\n".join(lines) + "\n"
