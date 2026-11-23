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


def test_offline_run_rescores_from_the_daily_table(tmp_path, monkeypatch):
    import json

    from floodwatch import config, events

    rng = np.random.default_rng(1)
    days = pd.date_range("2019-04-01", "2020-11-30", freq="D")
    rain = pd.Series(rng.gamma(0.8, 12.0, len(days)), index=days)
    floods = _days("2019-08-10", "2020-07-20", "2020-09-05")
    rain.loc[floods] = 250.0  # flood days are very wet
    daily = pd.DataFrame({"day_max": rain * 1.3, "day_mean": rain})
    daily["prev_3d"] = rain.shift(1).rolling(3).sum()
    daily["prev_7d"] = rain.shift(1).rolling(7).sum()
    daily["day_plus_prev_3d"] = rain + daily["prev_3d"]
    daily["tide_max"] = 1.0
    daily["tide_range"] = 2.0
    monkeypatch.setattr(config, "DERIVED_DIR", tmp_path)
    daily.rename_axis("date").to_csv(tmp_path / "daily_features_chirps.csv")
    (tmp_path / "hindcast_results.json").write_text(json.dumps({"tide_fit_check": {"rmse_m": 0.047}}))
    catalogue = pd.DataFrame(
        {"date": floods, "date_confidence": "exact", "coastal": [True, False, False]}
    )
    monkeypatch.setattr(events, "load_catalogue", lambda: catalogue)

    res = hindcast.run(2019, offline=True)

    assert res["tide_fit_check"] == {"rmse_m": 0.047}  # carried over, not recomputed
    assert res["chirps"]["floods_scored"] == ["2019-08-10", "2020-07-20", "2020-09-05"]
    assert res["chirps"]["seasons"] == 2
    assert res["chirps"]["skill"]["day_mean"]["auc"] > 0.95
    assert (tmp_path / "hindcast_tables.md").exists()
