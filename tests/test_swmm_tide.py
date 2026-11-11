"""SWMM with a sea-level boundary at the outfall: .inp text, behaviour, and a
re-run of committed tide results."""
from pathlib import Path

import pytest

from sgdrain import coastal, hyetograph, pipeline, rational, swmm_model, tide_pipeline
from conftest import read_csv, read_json

REPO = Path(__file__).resolve().parents[1]


def _lines(text, name):
    block = text.split(f"[{name}]")[1].split("\n[")[0]
    return [ln for ln in block.strip().splitlines() if ln.strip()]


def _inp(net, secs, T, outfall=None, hy=None, report_series=True):
    inv = rational.inverts(net, secs)
    if hy is None:
        hy = hyetograph.alternating_block(T, pipeline.STORM_DURATION_MIN, pipeline.STORM_DT_MIN)
    return swmm_model.build_inp(net, secs, inv, hy, pipeline.STORM_DT_MIN, "test", outfall=outfall,
                                report_series=report_series)


def _run(tmp_path, name, text):
    p = tmp_path / f"{name}.inp"
    p.write_text(text)
    return swmm_model.run_inp_series(p, links=["M4"] + (["PUMP1", "GATE"] if "[PUMPS]" in text else []),
                                     nodes=["OF", "J4", "J3", "J1"])


def test_default_text_is_unchanged(net, secs, T):
    text = _inp(net, secs, T, report_series=False).replace("test\n", "sg-drainage-swmm scenario design_10yr\n", 1)
    assert text == (REPO / "results" / "models" / "design_10yr.inp").read_text()


def test_timeseries_outfall_text(net, secs, T):
    inv = rational.inverts(net, secs)
    series = [(0, 8.0), (5, 8.05), (10, 8.1)]
    text = _inp(net, secs, T, {"type": "TIMESERIES", "series": series, "gated": True})
    assert _lines(text, "OUTFALLS") == [f"OF  {inv['M4']['inv_dn']:.4f}  TIMESERIES  TIDE  YES"]
    tide_rows = [ln.split() for ln in _lines(text, "TIMESERIES") if ln.startswith("TIDE")]
    assert [(r[1], float(r[2])) for r in tide_rows] == [("0:00", 8.0), ("0:05", 8.05), ("0:10", 8.1)]
    assert "NODES ALL" in text and "LINKS ALL" in text
    # an open outfall fills every junction up to the given level, within its depth
    text = _inp(net, secs, T, {"type": "TIMESERIES", "series": series, "gated": False, "init_level": 8.3})
    assert "TIMESERIES  TIDE  NO" in text
    for ln in _lines(text, "JUNCTIONS"):
        nid, z, ymax, y0 = ln.split()[:4]
        assert float(y0) == pytest.approx(min(max(0.0, 8.3 - float(z)), float(ymax)), abs=1e-4)
    assert any(float(ln.split()[3]) > 0 for ln in _lines(text, "JUNCTIONS"))


def test_fixed_and_pumped_text(net, secs, T):
    inv = rational.inverts(net, secs)
    text = _inp(net, secs, T, {"type": "FIXED", "stage": 8.25})
    assert _lines(text, "OUTFALLS") == [f"OF  {inv['M4']['inv_dn']:.4f}  FIXED  8.2500  NO"]
    text = _inp(net, secs, T, {"type": "PUMPED", "stage": 8.6, "pump_m3s": 4.5, "sump_area_m2": 700.0})
    outs = [ln.split() for ln in _lines(text, "OUTFALLS")]
    assert outs[0][0] == "SEA" and outs[0][2:] == ["FIXED", "8.6000", "YES"]
    assert outs[1][0] == "SEA_P" and outs[1][2:] == ["FREE", "NO"]
    st = _lines(text, "STORAGE")[0].split()
    assert st[0] == "OF" and st[4] == "FUNCTIONAL" and float(st[7]) == 700.0
    assert _lines(text, "PUMPS") == ["PUMP1  OF  SEA_P  PCURVE  ON  0  0"]
    curve = [ln.split() for ln in _lines(text, "CURVES")]
    assert curve[0][1] == "PUMP4" and float(curve[1][2]) == 4.5 and float(curve[-1][2]) == 4.5
    assert not any(ln.startswith("OF ") for ln in _lines(text, "JUNCTIONS"))


def test_bad_outfall_requests_raise(net, secs, T):
    for bc in ({"type": "TIDAL"}, {"type": "FIXED"}, {"type": "TIMESERIES"}, {"type": "PUMPED"}):
        with pytest.raises(ValueError):
            _inp(net, secs, T, bc)


def test_sea_below_the_outfall_invert_is_a_free_outfall(net, secs, T, tmp_path):
    inv = rational.inverts(net, secs)
    low = [(t, inv["M4"]["inv_dn"] - 0.5 + 0.001 * t) for t in range(0, 245, 5)]
    r0, s0 = _run(tmp_path, "free", _inp(net, secs, T))
    r1, s1 = _run(tmp_path, "low", _inp(net, secs, T, tide_pipeline.tidal_outfall(low, False)))
    assert r1.total_flood_volume_m3 == r0.total_flood_volume_m3
    assert r1.links == r0.links
    assert {k: v["max_hgl"] for k, v in r1.nodes.items() if k != "OF"} == \
        {k: v["max_hgl"] for k, v in r0.nodes.items() if k != "OF"}
    assert s1["link_flow"]["M4"] == s0["link_flow"]["M4"]


def test_flap_gate_stops_backflow(net, secs, T, tmp_path):
    inv = rational.inverts(net, secs)
    dry = [0.0] * 24
    high = inv["M4"]["inv_dn"] + 0.8                # sea 0.8 m above the outfall invert, no rain
    _, open_ = _run(tmp_path, "open", _inp(net, secs, T, {"type": "FIXED", "stage": high}, hy=dry))
    _, gated = _run(tmp_path, "gated", _inp(net, secs, T, {"type": "FIXED", "stage": high,
                                                            "gated": True}, hy=dry))
    assert min(open_["link_flow"]["M4"]) < -0.05     # the sea runs into the drains
    assert max(open_["node_head"]["J4"]) > inv["M4"]["inv_up"] + 0.5
    assert min(gated["link_flow"]["M4"]) > -1e-6     # the gate keeps it out
    assert max(gated["node_head"]["J4"]) < inv["M4"]["inv_up"] + 0.01


def test_pumped_run_matches_committed_verification(net, secs, T, tmp_path):
    ver = read_json("tide_summary.json")["pump"]["storms"]["design_10yr_design"]["verification"]
    bc = {"type": "PUMPED", "stage": ver["sea_level_local"], "pump_m3s": ver["pump_m3s"],
          "sump_area_m2": ver["sump_area_m2"]}
    res, ser = _run(tmp_path, "pumped", _inp(net, secs, T, bc))
    assert max(ser["link_flow"]["PUMP1"]) <= ver["pump_m3s"] + 1e-3
    assert max(abs(v) for v in ser["link_flow"]["GATE"]) < 1e-6          # the sea keeps the gate shut
    assert max(ser["node_head"]["OF"]) < ver["sea_level_local"]
    assert res.total_flood_volume_m3 == pytest.approx(ver["gate_shut_pumped"]["flood_m3"], abs=2)
    assert "PUMP1" in res.pumps and "PUMP1" not in res.links
    assert ver["gate_shut_pumped"]["d_flood_m3"] <= 0 < ver["gate_shut_no_pump"]["d_flood_m3"]


def _run_all_nodes(tmp_path, name, text, net):
    p = tmp_path / f"{name}.inp"
    p.write_text(text)
    return swmm_model.run_inp_series(p, links=["M4"], nodes=list(net.nodes))


@pytest.mark.parametrize("level", [-0.10, 0.0])
def test_committed_sweep_rows_reproduce(net, secs, T, tmp_path, level):
    ctx = tide_pipeline.tide_context(net)
    series = tide_pipeline.shifted_series(ctx, level)
    free = _run_all_nodes(tmp_path, "free", _inp(net, secs, T), net)
    tidal = _run_all_nodes(tmp_path, f"lvl{level}",
                           _inp(net, secs, T, tide_pipeline.tidal_outfall(series, False)), net)
    c = tide_pipeline.compare(net, *tidal, *free)
    row = next(r for r in read_csv("tide_level_sweep.csv")
               if float(r["hw_minus_outfall_ground_m"]) == pytest.approx(level))
    assert c["d_flood_m3"] == pytest.approx(float(row["d_flood_m3_open"]), abs=1.0)
    assert c["d_flood_m3"] == pytest.approx(tidal[0].total_flood_volume_m3 - free[0].total_flood_volume_m3,
                                            abs=0.05)
    assert c["max_head_rise_m"] == pytest.approx(float(row["max_head_rise_m_open"]), abs=2e-3)
    assert c["swmm_extent_m"] == float(row["swmm_extent_m_open"])
    assert c["raised_nodes"] == row["raised_nodes_open"].split(";")
    assert "OF" not in c["raised_nodes"]                       # the boundary node is not "raised"
    assert c["max_head_rise_m"] == pytest.approx(
        max(max(tidal[1]["node_head"][n]) - max(free[1]["node_head"][n]) for n in net.nodes if n != "OF"),
        abs=1e-3)
