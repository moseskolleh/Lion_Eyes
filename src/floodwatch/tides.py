"""Astronomical tide for Freetown at any date.

Modelled sea level is only available from 2023. Tides, however, repeat on
fixed astronomical cycles, so we fit tidal constituents (M2, S2, K1, O1, ...)
to the recent series with UTide, which also applies the 18.6-year nodal
corrections, and then predict the tide for any past or future hour.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import utide

from floodwatch.config import DERIVED_DIR, RAW_DIR, SEA_POINT


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


# The fitted constituents are committed so that predictions (e.g. the daily
# Outlook in CI) need no sea-level download.
COEF_JSON = DERIVED_DIR / "tide_constituents.json"


def _encode(value):
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items() if k != "weights"}  # weights: fit-only, large
    if isinstance(value, np.ndarray):
        return {"__array__": value.tolist(), "dtype": str(value.dtype)}
    if isinstance(value, np.generic):
        return value.item()
    return value


def _decode(value):
    if isinstance(value, dict):
        if "__array__" in value:
            return np.array(value["__array__"], dtype=value["dtype"])
        return utide.utilities.Bunch({k: _decode(v) for k, v in value.items()})
    return value


def save(coef: utide.utilities.Bunch, path=COEF_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_encode(coef), indent=1))


def load(path=COEF_JSON) -> utide.utilities.Bunch:
    return _decode(json.loads(path.read_text()))


def model() -> utide.utilities.Bunch:
    """The tide model: committed constituents if present, else fit and save."""
    if COEF_JSON.exists():
        return load()
    sea = pd.read_csv(RAW_DIR / "tables" / "sea_level.csv.gz", parse_dates=["time"])
    coef = fit(sea)
    save(coef)
    return coef
