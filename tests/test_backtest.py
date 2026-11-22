from datetime import date, timedelta

import pandas as pd

from floodwatch import backtest


def _rows(issue: date, levels: list[str], p_wet: list[float]) -> list[dict]:
    return [{"issue": issue, "lead_day": k, "day": issue + timedelta(days=k - 1), "level": lvl,
             "p_wet": p, "p_very_wet": 0.0, "prior_3d_mm": 10.0, "median_mm": 5.0,
             "observed_mm": 5.0, "wet_mm": 30.0}
            for k, (lvl, p) in enumerate(zip(levels, p_wet), 1)]


def test_score_counts_warnings_before_floods_and_on_ordinary_days():
    flood = date(2025, 8, 10)
    sample = [date(2025, 7, 1), date(2025, 7, 2)]
    rows = []
    rows += _rows(flood - timedelta(days=2), ["LOW", "LOW", "LOW"], [0, 0, 0])
    rows += _rows(flood - timedelta(days=1), ["LOW", "HIGH", "LOW"], [0, 0.6, 0])  # tomorrow (the flood day) HIGH
    rows += _rows(flood, ["ELEVATED", "LOW", "LOW"], [0.4, 0, 0])
    rows += _rows(sample[0], ["LOW", "LOW", "LOW"], [0, 0, 0])
    rows += _rows(sample[1], ["LOW", "ELEVATED", "LOW"], [0, 0.35, 0])
    r = backtest.score(pd.DataFrame(rows), sample, [flood])
    assert r["floods"]["day_before"] == {"elevated_or_high": 1, "high": 1, "of": 1}
    assert r["floods"]["same_morning"] == {"elevated_or_high": 1, "high": 0, "of": 1}
    assert r["floods"]["two_days_before"]["elevated_or_high"] == 0
    assert r["ordinary_days"]["elevated_or_high"] == 0.5
    assert r["ordinary_days"]["alerts_from_forecast"] == 1
