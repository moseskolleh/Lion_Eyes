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
    assert "**HIGH**" in text and "Kroo Bay, Portor" in text
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
