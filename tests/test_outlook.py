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
