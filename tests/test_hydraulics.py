import itertools
import math

import pytest

from sgdrain import cop
from sgdrain import hydraulics as hy

N = cop.MANNING_N["concrete"]


def test_manning_hand_calculation():
    # b = 1 m, y = 0.5 m: A = 0.5, P = 2.0, R = 0.25; S = 0.001, n = 0.015
    expected = (1 / 0.015) * 0.5 * 0.25 ** (2 / 3) * 0.001 ** 0.5
    assert expected == pytest.approx(0.418317, rel=1e-5)
    assert hy.manning_q(1.0, 0.5, 0.001, 0.015) == pytest.approx(expected, rel=1e-12)


def test_geometry_of_open_rectangle():
    assert hy.area(1.2, 0.5) == pytest.approx(0.6)
    assert hy.wetted_perimeter(1.2, 0.5) == pytest.approx(2.2)
    assert hy.hydraulic_radius(1.2, 0.5) == pytest.approx(0.6 / 2.2)


@pytest.mark.parametrize("s", [1 / 1000, 1 / 300, 1 / 100])
def test_capacity_monotonic_in_width_and_depth(s):
    widths = [0.6 + 0.1 * k for k in range(25)]
    depths = [0.6 + 0.1 * k for k in range(15)]
    for d in depths:
        q = [hy.capacity_with_freeboard(b, d, s, N, cop.FREEBOARD_FRACTION) for b in widths]
        assert all(b > a for a, b in zip(q, q[1:]))
    for b in widths:
        q = [hy.capacity_with_freeboard(b, d, s, N, cop.FREEBOARD_FRACTION) for d in depths]
        assert all(b2 > a for a, b2 in zip(q, q[1:]))


def test_capacity_monotonic_in_slope_and_roughness():
    slopes = [1 / 1000, 1 / 600, 1 / 400, 1 / 300, 1 / 200, 1 / 100]
    q = [hy.manning_q(1.0, 0.6, s, N) for s in slopes]
    assert all(b > a for a, b in zip(q, q[1:]))
    # Q scales with sqrt(S)
    assert q[-1] / q[0] == pytest.approx(math.sqrt(10), rel=1e-12)
    ns = sorted(cop.MANNING_N.values())
    qn = [hy.manning_q(1.0, 0.6, 1 / 300, n) for n in ns]
    assert all(b < a for a, b in zip(qn, qn[1:]))


def test_continuity_q_equals_v_times_a():
    for b, y, s in itertools.product([0.6, 1.3, 2.4], [0.2, 0.7, 1.4], [1 / 500, 1 / 150]):
        assert hy.manning_q(b, y, s, N) == pytest.approx(hy.manning_v(b, y, s, N) * b * y, rel=1e-12)


def test_normal_depth_is_inverse_of_manning():
    for b, s, q in itertools.product([0.6, 1.1, 2.0], [1 / 600, 1 / 300, 1 / 150], [0.05, 0.4, 2.0, 6.0]):
        y = hy.normal_depth(q, b, s, N)
        assert hy.manning_q(b, y, s, N) == pytest.approx(q, rel=1e-8)
    assert hy.normal_depth(0.0, 1.0, 0.003, N) == 0.0


def test_capacity_with_freeboard_uses_85_percent_depth():
    b, d, s = 1.2, 1.0, 1 / 300
    assert hy.capacity_with_freeboard(b, d, s, N, 0.15) == pytest.approx(hy.manning_q(b, 0.85, s, N))
    assert hy.capacity_with_freeboard(b, d, s, N, 0.15) < hy.manning_q(b, d, s, N)


def test_froude_and_critical_depth():
    assert hy.froude(1.0, 0.1) == pytest.approx(1 / math.sqrt(9.81 * 0.1))
    q, b = 1.5, 1.2
    yc = hy.critical_depth(q, b)
    v = q / (b * yc)
    assert hy.froude(v, yc) == pytest.approx(1.0, rel=1e-9)
