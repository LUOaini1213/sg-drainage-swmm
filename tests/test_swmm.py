import re

import pytest

from sgdrain import cop, pipeline, swmm_model
from conftest import read_csv, read_json

THRESHOLD = 1.0  # % - SWMM continuity errors must stay below this


def _section_lines(text, name):
    block = text.split(f"[{name}]")[1].split("\n[")[0]
    return [ln for ln in block.strip().splitlines() if ln.strip() and not ln.startswith(";")]


def test_inp_reflects_the_design(net, secs, swmm_design):
    _, text = swmm_design
    subs = _section_lines(text, "SUBCATCHMENTS")
    assert len(subs) == len(net.subcatchments)
    assert sum(float(ln.split()[3]) for ln in subs) == pytest.approx(net.total_area_ha, rel=1e-6)
    for ln, s in zip(subs, net.subcatchments):
        p = ln.split()
        assert p[2] == s.outlet
        assert float(p[4]) == pytest.approx(swmm_model.pct_impervious(s.fractions), abs=0.01)
        assert float(p[5]) == pytest.approx(s.area_ha * 1e4 / s.overland_length_m, rel=1e-4)
    conds = _section_lines(text, "CONDUITS")
    assert len(conds) == len(net.reaches)
    for ln in conds:
        p = ln.split()
        assert float(p[4]) == cop.MANNING_N["concrete"]
        r = net.reach(p[0])
        assert float(p[3]) == pytest.approx(r.length, rel=1e-6)
        assert float(p[5]) - float(p[6]) == pytest.approx(secs[r.id][2] * r.length, abs=2e-4)
    xs = {ln.split()[0]: ln.split() for ln in _section_lines(text, "XSECTIONS")}
    for rid, (b, d, _) in secs.items():
        assert xs[rid][1] == "RECT_OPEN"
        assert float(xs[rid][2]) == d and float(xs[rid][3]) == b
    # rainfall in the time series integrates to the IDF depth
    ts = [float(ln.split()[2]) for ln in _section_lines(text, "TIMESERIES")]
    depth = sum(ts[:-1]) * pipeline.STORM_DT_MIN / 60
    from sgdrain import idf
    assert depth == pytest.approx(idf.depth_mm(10, pipeline.STORM_DURATION_MIN), rel=1e-4)


def test_pct_impervious_mapping():
    assert swmm_model.pct_impervious({"road": 1, "urban": 0, "vegetated": 0}) == pytest.approx(100)
    assert swmm_model.pct_impervious({"road": 0, "urban": 1, "vegetated": 0}) == pytest.approx(90)
    assert swmm_model.pct_impervious({"road": 0, "urban": 0, "vegetated": 1}) == pytest.approx(0)


def test_swmm_continuity_and_mass_balance(swmm_design):
    res, _ = swmm_design
    assert abs(res.runoff_continuity_pct) < THRESHOLD
    assert abs(res.routing_continuity_pct) < THRESHOLD
    assert res.total_precip_mm == pytest.approx(
        pipeline.idf.depth_mm(10, pipeline.STORM_DURATION_MIN), abs=0.01)
    assert 0 < res.runoff_coefficient <= 1


def test_swmm_rerun_matches_committed_results(design, swmm_design):
    res, _ = swmm_design
    rows = {r["reach"]: r for r in read_csv("swmm_vs_rational.csv")}
    for r in design:
        committed = float(rows[r.reach]["swmm_peak_m3s"])
        assert res.links[r.reach]["max_flow"] == pytest.approx(committed, rel=0.01)
        assert float(rows[r.reach]["rational_q_m3s"]) == pytest.approx(r.q_m3s, rel=1e-3)
    s = read_json("swmm_summary.json")
    flooded = sorted(n for n, v in res.nodes.items() if v["hours_flooded"] > 0)
    assert flooded == sorted(s["design"]["flooded_nodes"])
    assert res.total_flood_volume_m3 == pytest.approx(s["design"]["flood_volume_m3"], rel=0.05, abs=5)


def test_swmm_peaks_exceed_rational_as_reported(design, swmm_design):
    res, _ = swmm_design
    ratios = [res.links[r.reach]["max_flow"] / r.q_m3s for r in design]
    s = read_json("swmm_summary.json")
    assert min(ratios) == pytest.approx(s["swmm_over_rational_min"], abs=0.01)
    assert max(ratios) == pytest.approx(s["swmm_over_rational_max"], abs=0.01)


def test_every_logged_swmm_run_has_small_continuity_error():
    log = read_json("swmm_run_log.json")
    assert log["n_runs"] == len(log["runs"]) > 30
    for r in log["runs"]:
        assert abs(r["runoff"]) < THRESHOLD and abs(r["routing"]) < THRESHOLD, r
    assert log["max_abs_continuity_error_pct"] == max(
        max(abs(r["runoff"]), abs(r["routing"])) for r in log["runs"])


def test_report_parser_handles_no_flooding():
    text = """
  Runoff Quantity Continuity     hectare-m            mm
  Total Precipitation ......         1.000       100.000
  Surface Runoff ...........         0.900        90.000
  Continuity Error (%) .....        -0.010
  Flow Routing Continuity        hectare-m      10^6 ltr
  Continuity Error (%) .....         0.020

  ******************
  Node Depth Summary
  ******************

  ---------------------------------------------------------------------------------
                                 Average  Maximum  Maximum  Time of Max    Reported
                                   Depth    Depth      HGL   Occurrence   Max Depth
  Node                 Type       Meters   Meters   Meters  days hr:min      Meters
  ---------------------------------------------------------------------------------
  J1                   JUNCTION     0.10     0.50    10.00     0  01:00        0.50

  *********************
  Node Flooding Summary
  *********************

  No nodes were flooded.

  ***********************
  Link Flow Summary
  ***********************

  -----------------------------------------------------------------------------
                                 Maximum  Time of Max   Maximum    Max/    Max/
                                  |Flow|   Occurrence   |Veloc|    Full    Full
  Link                 Type          CMS  days hr:min     m/sec    Flow   Depth
  -----------------------------------------------------------------------------
  M1                   CONDUIT     1.000     0  00:57      1.50    0.80    0.70
"""
    res = swmm_model.parse_rpt(text)
    assert res.runoff_continuity_pct == -0.01 and res.routing_continuity_pct == 0.02
    assert res.nodes["J1"]["hours_flooded"] == 0 and res.total_flood_volume_m3 == 0
    assert res.links["M1"]["max_flow"] == 1.0
    assert res.runoff_coefficient == pytest.approx(0.9)
    assert re.search("Continuity", text)
