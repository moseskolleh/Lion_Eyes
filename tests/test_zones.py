import pandas as pd
import pytest

from floodwatch import zones


def test_zone_daily_rain_is_area_weighted(tmp_path, monkeypatch):
    monkeypatch.setattr(zones.config, "DERIVED_DIR", tmp_path)
    pd.DataFrame(
        {"zone_id": [1, 1, 2], "lat": [8.475, 8.475, 8.425], "lon": [-13.225, -13.275, -13.225],
         "weight": [0.75, 0.25, 1.0]}
    ).to_csv(tmp_path / "zone_chirps_weights.csv", index=False)
    day = pd.Timestamp("2022-08-28")
    cells = pd.DataFrame(
        {"date": [day] * 3, "lat": [8.475, 8.475, 8.425], "lon": [-13.225, -13.275, -13.225],
         "precip_mm": [100.0, 20.0, 50.0]}
    )
    rain = zones.zone_daily_rain(cells)
    assert rain.at[day, 1] == pytest.approx(0.75 * 100 + 0.25 * 20)
    assert rain.at[day, 2] == pytest.approx(50.0)


def test_zone_daily_rain_ignores_sea_cells(tmp_path, monkeypatch):
    monkeypatch.setattr(zones.config, "DERIVED_DIR", tmp_path)
    pd.DataFrame(
        {"zone_id": [1, 1], "lat": [8.475, 8.475], "lon": [-13.225, -13.275], "weight": [0.5, 0.5]}
    ).to_csv(tmp_path / "zone_chirps_weights.csv", index=False)
    day = pd.Timestamp("2022-08-28")
    cells = pd.DataFrame(
        {"date": [day] * 2, "lat": [8.475, 8.475], "lon": [-13.225, -13.275], "precip_mm": [40.0, -9999.0]}
    )
    # The sea cell is dropped and the remaining weight renormalised.
    assert zones.zone_daily_rain(cells).at[day, 1] == pytest.approx(40.0)
