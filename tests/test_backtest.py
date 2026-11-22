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
    r = backtest.score(pd.DataFrame(rows), sample, [flood], reported={"2025-08-10": ("2025-08-10 04:00", "")})
    assert r["floods"]["day_before"] == {"elevated_or_high": 1, "high": 1, "of": 1}
    assert r["floods"]["same_morning"] == {"elevated_or_high": 1, "high": 0, "of": 1}
    assert r["floods"]["two_days_before"]["elevated_or_high"] == 0
    # Reported at 04:00, before the morning issue: only the day-before Outlook was in time.
    assert r["per_flood"][0]["in_time_from"] == "day before" and r["per_flood"][0]["in_time"] == "HIGH"
    assert r["ordinary_days"]["elevated_or_high"] == 0.5
    assert r["ordinary_days"]["alerts_from_forecast"] == 1


def test_latest_issue_before_a_flood():
    flood = date(2025, 7, 31)
    # Pre-dawn flood: the evening issue the day before.
    assert backtest._latest_issue(flood, pd.Timestamp("2025-07-31 06:00")) == ("evening", date(2025, 7, 30))
    # Afternoon flood: that morning's issue.
    assert backtest._latest_issue(flood, pd.Timestamp("2025-07-31 18:00")) == ("morning", flood)
    # Late-night flood: that evening's issue.
    assert backtest._latest_issue(flood, pd.Timestamp("2025-07-31 23:30")) == ("evening", flood)
    # Unknown time: the evening before, which comes before any hour of the flood day.
    assert backtest._latest_issue(flood, None) == ("evening", date(2025, 7, 30))
