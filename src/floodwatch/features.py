"""Turn hourly rain and tide into one row of features per day.

Intensity features use the wettest grid cell over the peninsula in each hour,
because a flash flood needs only one hillside to get a downpour. Wetness
("antecedent") features use the average over cells.
"""

from __future__ import annotations

import pandas as pd

INTENSITY_WINDOWS_H = (1, 3, 6)


def hourly_rain_fields(rain: pd.DataFrame) -> pd.DataFrame:
    """From long hourly rain (time, point, precip_mm) build hourly fields.

    Returns a frame indexed by hour with columns ``rain_{n}h_max`` (wettest
    cell's n-hour total ending that hour) and ``rain_1h_mean``.
    """
    wide = rain.pivot_table(index="time", columns="point", values="precip_mm")
    full = pd.date_range(wide.index.min(), wide.index.max(), freq="h")
    wide = wide.reindex(full)
    out = pd.DataFrame(index=full)
    for n in INTENSITY_WINDOWS_H:
        out[f"rain_{n}h_max"] = wide.rolling(n, min_periods=n).sum().max(axis=1)
    out["rain_1h_mean"] = wide.mean(axis=1)
    return out


def daily_features(hourly: pd.DataFrame, tide: pd.Series | None = None) -> pd.DataFrame:
    """One row per UTC day.

    Columns: max 1/3/6-hour rain, 24-hour total, rain in the previous 3 and 7
    days, and (if ``tide`` is given) the day's highest tide, tidal range and
    the tide at the hour the heaviest 3-hour burst ended.
    """
    day = hourly.index.floor("D")
    grouped = hourly.groupby(day)
    daily = pd.DataFrame(
        {f"max_{n}h": grouped[f"rain_{n}h_max"].max() for n in INTENSITY_WINDOWS_H}
    )
    daily["total_24h"] = grouped["rain_1h_mean"].sum(min_count=20)
    daily["prev_3d"] = daily["total_24h"].shift(1).rolling(3, min_periods=3).sum()
    daily["prev_7d"] = daily["total_24h"].shift(1).rolling(7, min_periods=7).sum()

    if tide is not None:
        tide = tide.reindex(hourly.index)
        tgroup = tide.groupby(day)
        daily["tide_max"] = tgroup.max()
        daily["tide_range"] = tgroup.max() - tgroup.min()
        rain3 = hourly["rain_3h_max"].dropna()
        peak_hour = rain3.groupby(rain3.index.floor("D")).idxmax()
        daily["tide_at_peak"] = tide.reindex(peak_hour.to_numpy()).set_axis(peak_hour.index)

    daily.index.name = "date"
    return daily
