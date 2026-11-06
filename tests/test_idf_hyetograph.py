import json
import math
import sys
from pathlib import Path

import pytest

from sgdrain import hyetograph, idf

REPO = Path(__file__).resolve().parents[1]


def test_digitised_table_is_monotonic():
    durations, table = idf.load_table()
    periods = sorted(table)
    assert periods == [2, 3, 5, 10, 15, 25, 50, 100]
    for T in periods:
        v = table[T]
        assert all(b < a for a, b in zip(v, v[1:])), f"T={T} not decreasing in duration"
        # depth (i * d) must increase with duration for the hyetograph to exist
        dep = [i * d for i, d in zip(v, durations)]
        assert all(b > a for a, b in zip(dep, dep[1:]))
    for j in range(len(durations)):
        col = [table[T][j] for T in periods]
        assert all(b > a for a, b in zip(col, col[1:])), f"duration {durations[j]} not increasing in T"


def test_interpolation_exact_at_nodes_and_loglog_between():
    durations, table = idf.load_table()
    for j, d in enumerate(durations):
        assert idf.intensity(10, d) == pytest.approx(table[10][j], rel=1e-12)
    d1, d2 = durations[5], durations[6]
    mid = math.sqrt(d1 * d2)
    assert idf.intensity(10, mid) == pytest.approx(math.sqrt(table[10][5] * table[10][6]), rel=1e-9)


def test_uplift_is_multiplicative_and_range_checked():
    assert idf.intensity(10, 17.3, 0.25) == pytest.approx(1.25 * idf.intensity(10, 17.3), rel=1e-12)
    with pytest.raises(ValueError):
        idf.intensity(10, 2.0)
    with pytest.raises(KeyError):
        idf.intensity(7, 10.0)


def test_digitisation_metadata_matches_tool():
    meta = json.loads((REPO / "data" / "idf_digitisation_meta.json").read_text())
    sys.path.insert(0, str(REPO / "tools"))
    try:
        import digitize_idf
    finally:
        sys.path.pop(0)
    assert meta["pdf_sha256"] == digitize_idf.EXPECTED_SHA256
    assert meta["one_pixel_reading_uncertainty_pct"] < 1.0
    assert meta["max_local_fit_residual_px"] < 2.0


@pytest.mark.parametrize("T,dur,dt", [(10, 120, 5), (100, 60, 5), (10, 115, 5)])
def test_alternating_block_properties(T, dur, dt):
    blocks = hyetograph.alternating_block(T, dur, dt)
    n = dur // dt
    assert len(blocks) == n
    depths = [b * dt / 60 for b in blocks]
    cum = [idf.depth_mm(T, k * dt) for k in range(1, n + 1)]
    inc = [cum[0]] + [cum[k] - cum[k - 1] for k in range(1, n)]
    # the blocks are a permutation of the IDF depth increments
    assert sorted(depths) == pytest.approx(sorted(inc), rel=1e-12)
    assert sum(depths) == pytest.approx(cum[-1], rel=1e-9)
    c = (n - 1) // 2
    assert blocks.index(max(blocks)) == c
    assert max(blocks) == pytest.approx(idf.intensity(T, dt), rel=1e-9)
    top = sorted(inc, reverse=True)
    for k in range(1, n + 1):
        # the central window of k blocks (growing right, then left) holds the
        # k largest increments ...
        lo = c - (k - 1) // 2
        hi = c + k // 2
        if hi >= n:                       # right side exhausted: grow left only
            hi, lo = n - 1, n - k
        window = depths[lo:hi + 1]
        assert sum(window) == pytest.approx(sum(top[:k]), rel=1e-9)
        # ... so the storm is at least as intense as the IDF curve for every
        # duration, and (with a digitised, nearly concave curve) only just
        assert sum(window) >= cum[k - 1] - 1e-9
        assert sum(window) <= cum[k - 1] * 1.01


def test_hyetograph_uplift_scales_every_block():
    a = hyetograph.alternating_block(10, 120, 5)
    b = hyetograph.alternating_block(10, 120, 5, uplift=0.5)
    assert all(y == pytest.approx(1.5 * x, rel=1e-12) for x, y in zip(a, b))
