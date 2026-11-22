import numpy as np
import pandas as pd

from floodwatch import tides


def test_fit_recovers_tide_and_predicts_outside_fit_period():
    # Synthetic semidiurnal tide: M2 (12.42 h) 0.9 m and S2 (12.00 h) 0.3 m.
    def tide_at(times: pd.DatetimeIndex) -> np.ndarray:
        hours = (times - pd.Timestamp("2000-01-01")).total_seconds() / 3600
        return 0.9 * np.cos(2 * np.pi * hours / 12.4206012) + 0.3 * np.cos(2 * np.pi * hours / 12.0)

    fit_times = pd.date_range("2023-01-01", "2023-12-31", freq="h")
    coef = tides.fit(pd.DataFrame({"time": fit_times, "sea_level_m": tide_at(fit_times)}))

    # Predict just after the fit period. (Far from it, UTide's 18.6-year nodal
    # corrections - right for real tides - would differ from this synthetic
    # constant-amplitude tide by a few cm.)
    later = pd.date_range("2024-02-01", periods=72, freq="h")
    error = tides.predict(coef, later).to_numpy() - tide_at(later)
    assert np.sqrt(np.mean(error**2)) < 0.02
