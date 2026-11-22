from datetime import date

import numpy as np
import pandas as pd

from floodwatch import outlook


def test_classify_levels():
    assert outlook.classify(p_wet=0.1, p_very_wet=0.0, prior_3d_mm=20) == "LOW"
    assert outlook.classify(p_wet=0.4, p_very_wet=0.1, prior_3d_mm=20) == "ELEVATED"
    assert outlook.classify(p_wet=0.0, p_very_wet=0.0, prior_3d_mm=150) == "ELEVATED"  # saturated ground
    assert outlook.classify(p_wet=0.5, p_very_wet=0.35, prior_3d_mm=20) == "HIGH"
    assert outlook.classify(p_wet=0.4, p_very_wet=0.1, prior_3d_mm=150) == "HIGH"  # wet on saturated ground


def test_transition_months_lower_thresholds():
    assert outlook._scaled(8) == (outlook.WET_DAY_MM, outlook.VERY_WET_DAY_MM)
    wet, very = outlook._scaled(5)
    assert wet < outlook.WET_DAY_MM and very < outlook.VERY_WET_DAY_MM


def test_high_tides_lists_only_high_waters_above_threshold():
    t = pd.date_range("2026-08-03", periods=6 * 24, freq="10min")
    hours = (t - t[0]).total_seconds() / 3600
    # Two high waters a day; the second is higher (diurnal inequality).
    level = 1.0 * np.cos(2 * np.pi * (hours - 6) / 12.42) + 0.25 * np.cos(2 * np.pi * (hours - 18) / 24.8)
    tide = pd.Series(level, index=t)
    highs = outlook._high_tides(tide, date(2026, 8, 3))
    assert len(highs) == 1 and highs[0].startswith("18:")


def test_bulletin_names_zones_and_people_when_not_low():
    o = {
        "issued": "2027-08-03", "forecast_run": "2027-08-03 00:00 UTC",
        "observed_rain_last_3_days_mm": 120.0, "observed_days": [{}, {}, {}],
        "days": [{"day": "2027-08-03", "level": "HIGH", "p_wet": 0.8, "p_very_wet": 0.5, "median_mm": 60.0,
                  "prior_3d_mm": 120.0, "high_tides": ["06:20 (1.3 m)"]}],
        "low_ground_zones": ["Kroo Bay", "Portor"], "steep_zones": ["Bathurst"],
        "people_low_ground": 5353, "people_steep": 722,
    }
    text = outlook.to_text(o)
    assert "**HIGH (act)**" in text and "**Act.**" in text and "Kroo Bay, Portor" in text
    assert "about 5,353 people" in text and "about 722 people on steep slopes" in text


def test_bulletin_says_when_wetness_is_unknown():
    o = {
        "issued": "2027-08-03", "forecast_run": "2027-08-03 00:00 UTC",
        "observed_rain_last_3_days_mm": None, "observed_days": [],
        "days": [{"day": "2027-08-03", "level": "LOW", "p_wet": 0.0, "p_very_wet": 0.0, "median_mm": 1.0,
                  "prior_3d_mm": 0.0, "high_tides": []}],
        "low_ground_zones": [], "steep_zones": [],
    }
    assert "not available" in outlook.to_text(o)


def _members(day_mm: dict[int, float], n: int = 51) -> pd.DataFrame:
    return pd.DataFrame([{"member": m, "day": k, "mean_mm": mm, "max_mm": mm}
                         for m in range(n) for k, mm in day_mm.items()])


def test_day_levels_chains_observed_rain_into_forecast_medians():
    days = outlook.day_levels(_members({1: 40.0, 2: 0.0, 3: 0.0}), date(2027, 8, 3), [50.0, 30.0, 25.0])
    assert [d["day"] for d in days] == [date(2027, 8, 3), date(2027, 8, 4), date(2027, 8, 5)]
    # Day 1: 105 mm in the 3 observed days (saturated) and every member wet -> HIGH.
    assert days[0]["prior_3d_mm"] == 105.0 and days[0]["level"] == "HIGH"
    # Day 2: the 3 days before are 30 + 25 observed + 40 forecast = 95 mm -> not saturated, dry -> LOW.
    assert days[1]["prior_3d_mm"] == 95.0 and days[1]["level"] == "LOW"


def test_evening_periods_run_noon_to_noon():
    start = pd.Timestamp("2027-08-02 12:00")
    assert outlook._period_label(start, start + pd.Timedelta(days=1), first=True) == "Tonight to noon Tue 03 Aug"
    later = start + pd.Timedelta(days=1)
    assert outlook._period_label(later, later + pd.Timedelta(days=1), first=False) == "Noon Tue 03 to noon Wed 04 Aug"
    midnight = pd.Timestamp("2027-08-03")
    assert outlook._period_label(midnight, midnight + pd.Timedelta(days=1), first=True) == "Tue 03 Aug"


def test_evening_bulletin_says_watch_and_points_to_next_issue():
    o = {
        "issued": "2027-08-02", "edition": "evening", "forecast_run": "2027-08-02 12:00 UTC",
        "observed_rain_last_3_days_mm": 40.0, "observed_period": "the last 2½ days", "observed_days": [{}, {}, {}],
        "days": [{"day": "2027-08-02", "start": "2027-08-02T12:00:00", "label": "Tonight to noon Tue 03 Aug",
                  "level": "ELEVATED", "p_wet": 0.4, "p_very_wet": 0.1, "median_mm": 25.0, "prior_3d_mm": 40.0,
                  "high_tides": []}],
        "low_ground_zones": ["Kroo Bay"], "steep_zones": ["Bathurst"],
    }
    text = outlook.to_text(o)
    assert "evening of 2027-08-02" in text and "Tonight to noon Tue 03 Aug" in text
    assert "**ELEVATED (watch)**" in text and "**Watch.**" in text and "tomorrow morning's update" in text
    assert "noon to noon" in text and "What the levels mean" in text


def test_short_message_fits_one_text_and_names_low_ground_when_high():
    days = [{"day": "2027-08-02", "start": "2027-08-02T12:00:00", "level": "HIGH"},
            {"day": "2027-08-03", "start": "2027-08-03T12:00:00", "level": "ELEVATED"},
            {"day": "2027-08-04", "start": "2027-08-04T12:00:00", "level": "LOW"}]
    o = {"issued": "2027-08-02", "edition": "evening", "days": days,
         "low_ground_zones": ["New Life Community", "Kaningo", "Tengbeh Town", "Kroo Bay"]}
    text = outlook.sms_text(o)
    assert len(text) <= outlook.SMS_LIMIT and text.isascii()
    assert text.startswith("Freetown flood outlook, 02 Aug pm: Tonight HIGH, Tomorrow ELEVATED, Wed LOW.")
    assert "ACT:" in text and "New Life Community" in text
    o["days"] = [dict(d, level="LOW") for d in days]
    assert "No action needed." in outlook.sms_text(o)
