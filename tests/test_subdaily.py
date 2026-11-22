import pandas as pd
import pytest

from floodwatch import subdaily
from floodwatch.sources import imerg


def _fake_days(burst_start: str, mm_per_half_hour: float, n_half_hours: int):
    """Three dry days over the peninsula cells with one burst on the wettest cell."""

    def fetch_days(days):
        times = pd.date_range(pd.Timestamp(min(days)), periods=48 * len(days), freq="30min")
        rows = []
        for t in times:
            for lat in subdaily.PEN_LATS:
                for lon in subdaily.PEN_LONS:
                    rate = 0.0
                    if (lat, lon) == (8.45, -13.25):
                        start = pd.Timestamp(burst_start)
                        if start <= t < start + pd.Timedelta(minutes=30 * n_half_hours):
                            rate = mm_per_half_hour * 2  # mm/h
                    rows.append((t, lat, lon, rate))
        return pd.DataFrame(rows, columns=["time", "lat", "lon", "rate_mm_h"])

    return fetch_days


def test_window_metrics_finds_burst_and_its_end(monkeypatch):
    # 6 half-hours of 10 mm each = 60 mm in 3 hours, 02:00-05:00 on the flood day.
    monkeypatch.setattr(imerg, "fetch_days", _fake_days("2019-08-02 02:00", 10.0, 6))
    m = subdaily.window_metrics(pd.Timestamp("2019-08-02"))
    assert m["max_1h"] == pytest.approx(20.0)
    assert m["max_3h"] == pytest.approx(60.0)
    assert m["max_24h"] == pytest.approx(60.0)
    assert m["peak_3h_ends"] == "2019-08-02 05:00:00"
    # One wet cell out of nine: the peninsula mean is a ninth.
    assert m["max_24h_mean"] == pytest.approx(60.0 / 9, abs=0.1)
