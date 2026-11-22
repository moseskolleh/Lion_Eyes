import numpy as np
import pandas as pd
import pytest

affine = pytest.importorskip("affine")

from floodwatch import population, terrain  # noqa: E402


def _hydrology(n: int = 10) -> terrain.Hydrology:
    shape = (n, n)
    return terrain.Hydrology(
        dem=np.ones(shape), upstream_km2=np.zeros(shape), streams=np.zeros(shape, bool),
        hand=np.zeros(shape), transform=affine.Affine(0.1, 0, 0.0, 0, -0.1, 1.0),
        fdir=np.zeros(shape), cell_km2=0.01,
    )


def test_building_counts_places_centres_on_the_grid():
    h = _hydrology()
    b = pd.DataFrame({"lon": [0.05, 0.06, 0.55, 2.0], "lat": [0.95, 0.94, 0.45, 2.0]})
    counts = population.building_counts(h, b)
    assert counts[0, 0] == 2  # two buildings in the top-left cell
    assert counts[5, 5] == 1
    assert counts.sum() == 3  # the one off the grid is ignored
