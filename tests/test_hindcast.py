import numpy as np
import pandas as pd

from floodwatch import hindcast


def _days(*isos: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(list(isos)))


def test_auc_extremes_and_chance():
    assert hindcast.auc(np.array([5.0, 6.0]), np.array([1.0, 2.0])) == 1.0
    assert hindcast.auc(np.array([1.0]), np.array([5.0])) == 0.0
    assert hindcast.auc(np.array([3.0]), np.array([3.0])) == 0.5


def test_window_max_spans_neighbouring_days():
    s = pd.Series([0.0, 1.0, 9.0, 2.0, 0.0, 0.0], index=pd.date_range("2020-07-31", periods=6, freq="D"))
    w = hindcast.window_max(s)
    assert w.loc["2020-08-03"] == 9.0  # yesterday's heavy rain counts
    assert w.loc["2020-08-01"] == 9.0  # so does tomorrow's (date ambiguity)
    assert w.loc["2020-08-04"] == 2.0


def test_score_rule_counts_hits_and_false_alarm_runs():
    idx = pd.date_range("2020-08-01", periods=10, freq="D")
    fires = pd.Series(False, index=idx)
    fires.loc["2020-08-02"] = True  # day before flood on the 3rd: hit
    fires.loc["2020-08-06":"2020-08-07"] = True  # one 2-day run, no flood: 1 false alarm
    flood_days = _days("2020-08-03", "2020-08-10")  # second flood missed
    s = hindcast.score_rule(fires, flood_days, seasons=1)
    assert (s.hits, s.floods, s.false_alarms) == (1, 2, 1)
    assert s.hit_rate == 0.5


def test_score_rule_ignores_days_outside_window():
    idx = pd.date_range("2020-08-01", periods=6, freq="D")
    fires = pd.Series(False, index=idx)
    fires.loc["2020-08-05"] = True  # two days after the flood
    s = hindcast.score_rule(fires, _days("2020-08-03"), seasons=1)
    assert (s.hits, s.false_alarms) == (0, 1)
