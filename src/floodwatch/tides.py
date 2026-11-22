"""Astronomical tide for Freetown at any date.

Modelled sea level is only available from 2023. Tides, however, repeat on
fixed astronomical cycles, so we fit tidal constituents (M2, S2, K1, O1, ...)
to the recent series with UTide, which also applies the 18.6-year nodal
corrections, and then predict the tide for any past or future hour.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import utide

from floodwatch.config import SEA_POINT


def fit(sea: pd.DataFrame) -> utide.utilities.Bunch:
    """Fit tidal constituents to hourly ``time``/``sea_level_m`` data."""
    clean = sea.dropna(subset=["sea_level_m"])
    return utide.solve(
        clean["time"].to_numpy(),
        clean["sea_level_m"].to_numpy(),
        lat=SEA_POINT.lat,
        method="ols",
        conf_int="none",
        trend=False,
        verbose=False,
    )


def predict(coef: utide.utilities.Bunch, times: pd.DatetimeIndex) -> pd.Series:
    """Predicted tide (m relative to mean sea level) at ``times``."""
    recon = utide.reconstruct(times.to_numpy(), coef, verbose=False)
    return pd.Series(np.asarray(recon.h), index=times, name="tide_m")
