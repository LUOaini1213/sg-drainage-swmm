"""Mass-curve (sequent-peak) storage for a pump behind a shut outfall gate."""
import pytest

from sgdrain import pumpsump
from conftest import read_csv, read_json


def _triangle(t_peak, t_end, q_peak):
    return [0.0, t_peak, t_end], [0.0, q_peak, 0.0]


@pytest.mark.parametrize("qp", [0.0, 1.5, 3.0, 4.5, 6.0, 7.0])
def test_triangle_closed_form(qp):
    t, q = _triangle(1200.0, 3600.0, 6.0)
    # storage = area of the part of the triangle above qp = 0.5 T Qpk (1 - qp/Qpk)^2
    expect = 0.5 * 3600.0 * 6.0 * (1 - qp / 6.0) ** 2 if qp < 6.0 else 0.0
    assert pumpsump.storage_required(t, q, qp) == pytest.approx(expect, rel=1e-12, abs=1e-9)


def test_crossing_inside_a_step_is_exact():
    t, q = _triangle(1200.0, 3600.0, 6.0)
    fine_t = [float(k) for k in range(0, 3601)]
    fine_q = [6.0 * x / 1200.0 if x <= 1200 else 6.0 * (3600.0 - x) / 2400.0 for x in fine_t]
    for qp in (1.0, 2.5, 5.0):
        assert pumpsump.storage_required(t, q, qp) == pytest.approx(
            pumpsump.storage_required(fine_t, fine_q, qp), rel=1e-9)


def test_sump_empties_between_separate_peaks():
    # two triangles with a dry gap long enough for a 3 m3/s pump to empty the sump
    t = [0.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0]
    q = [0.0, 6.0, 0.0, 0.0, 6.0, 0.0]
    one = pumpsump.storage_required([0.0, 1000.0, 2000.0], [0.0, 6.0, 0.0], 3.0)
    assert one == pytest.approx(0.5 * 2000.0 * 6.0 * 0.25)
    assert pumpsump.storage_required(t, q, 3.0) == pytest.approx(one)
    # back to back, inflow never drops below the pump rate between the peaks: storage adds up
    t2 = [0.0, 1000.0, 1500.0, 2500.0, 3500.0]
    q2 = [0.0, 6.0, 3.0, 6.0, 0.0]
    assert pumpsump.storage_required(t2, q2, 3.0) == pytest.approx(1500.0 + 1500.0 + 750.0)


def test_input_checks():
    with pytest.raises(ValueError):
        pumpsump.storage_required([0.0, 1.0], [1.0], 0.5)
    with pytest.raises(ValueError):
        pumpsump.storage_required([0.0, 1.0], [1.0, 2.0], -1.0)
    with pytest.raises(ValueError):
        pumpsump.storage_required([0.0, 0.0, 1.0], [1.0, 2.0, 1.0], 0.5)


def test_volume_and_bounds_on_the_committed_inflow():
    rows = read_csv("tide_outfall_inflow.csv")
    t = [float(r["t_s"]) for r in rows]
    for tag in [k for k in rows[0] if k != "t_s"]:
        q = [float(r[tag]) for r in rows]
        vol = pumpsump.volume(t, q)
        assert pumpsump.storage_required(t, q, 0.0) == pytest.approx(vol, rel=1e-9)
        assert pumpsump.storage_required(t, q, max(q)) == 0.0
        v = [pumpsump.storage_required(t, q, f * max(q)) for f in (0.2, 0.4, 0.6, 0.8, 1.0)]
        assert all(b < a for a, b in zip(v, v[1:]))


def test_committed_trade_off_reproduces():
    rows = read_csv("tide_outfall_inflow.csv")
    t = [float(r["t_s"]) for r in rows]
    s = read_json("tide_summary.json")["pump"]
    for tag, entry in s["storms"].items():
        q = [float(r[tag]) for r in rows]
        assert entry["peak_inflow_m3s"] == pytest.approx(max(q), abs=6e-4)
        assert entry["event_volume_m3"] == pytest.approx(pumpsump.volume(t, q), abs=0.051)
        for row in entry["trade_off"]:
            assert row["pump_m3s"] == pytest.approx(row["pump_fraction_of_peak"] * max(q), abs=6e-4)
            assert row["storage_m3"] == pytest.approx(
                pumpsump.storage_required(t, q, row["pump_fraction_of_peak"] * max(q)), abs=0.051)
    ver = s["storms"]["design_10yr_design"]["verification"]
    assert ver["sump_area_m2"] == pytest.approx(ver["storage_m3"] / ver["sump_depth_m"], abs=0.1)
