"""Consistency of the committed tide / sea-level results."""
import pytest

from sgdrain import backwater as bw, coastal, rational
from conftest import read_csv, read_json

THRESHOLD = 1.0


@pytest.fixture(scope="module")
def summ():
    return read_json("tide_summary.json")


@pytest.fixture(scope="module")
def inputs():
    return read_json("tide_inputs.json")


def test_scenario_grid_is_complete(summ):
    rows = read_csv("tide_scenarios.csv")
    ids = [s["id"] for s in coastal.SLR_SCENARIOS]
    combos = {(r["storm"], r["sizes"]) for r in rows}
    assert len(combos) == 7
    for st, sz in combos:
        for sid in ids:
            got = [r for r in rows if (r["storm"], r["sizes"], r["slr_id"]) == (st, sz, sid)]
            assert sorted(r["gated"] for r in got) == ["False", "True"]
    assert summ["base_n_runs"] + summ["base_n_sea_above_ground"] == len(rows)


def test_peak_levels_follow_the_datum_arithmetic(inputs):
    hw_now = inputs["datum"]["hw_now_shd"]
    g = inputs["datum"]["outfall_ground_shd"]
    for r in read_csv("tide_scenarios.csv"):
        assert float(r["peak_sea_level_shd"]) == pytest.approx(hw_now + float(r["slr_m"]), abs=2e-3)
        assert float(r["peak_below_outfall_ground_m"]) == pytest.approx(
            g - float(r["peak_sea_level_shd"]), abs=2e-3)
    for r in read_csv("tide_datum_sensitivity.csv"):
        assert float(r["peak_below_outfall_ground_m"]) == pytest.approx(
            float(r["outfall_ground_shd"]) - hw_now - float(r["slr_m"]), abs=2e-3)
        above = float(r["peak_below_outfall_ground_m"]) < 0
        assert (r["status"] == "sea above outfall ground") == above


def test_base_datum_sensitivity_row_repeats_the_scenario_run():
    base = coastal.OUTFALL_GROUND_SHD_BASE
    scen = {r["slr_id"]: r for r in read_csv("tide_scenarios.csv")
            if r["storm"] == "design_10yr" and r["gated"] == "False"}
    gated = {r["slr_id"]: r for r in read_csv("tide_scenarios.csv")
             if r["storm"] == "design_10yr" and r["gated"] == "True"}
    for r in read_csv("tide_datum_sensitivity.csv"):
        if float(r["outfall_ground_shd"]) == base and r["status"] == "run":
            assert float(r["d_flood_m3_open"]) == float(scen[r["slr_id"]]["d_flood_m3"])
            assert float(r["d_flood_m3_gated"]) == float(gated[r["slr_id"]]["d_flood_m3"])
            assert r["peak_sea_level_shd"] == scen[r["slr_id"]]["peak_sea_level_shd"]


def test_sea_below_the_invert_never_changes_anything():
    for name in ("tide_scenarios.csv", "tide_datum_sensitivity.csv"):
        for r in read_csv(name):
            if r["status"] == "run" and float(r["peak_above_outfall_invert_m"]) < 0:
                for k in [k for k in r if k.startswith("d_flood_m3") or k.startswith("max_head_rise")]:
                    assert float(r[k]) == 0.0, (name, r["slr_id"], k)
                assert r["gvf_fail_due_to_tide"] == ""


def test_every_tide_run_has_small_continuity_error():
    for r in read_csv("tide_scenarios.csv"):
        if r["status"] == "run":
            assert abs(float(r["runoff_continuity_pct"])) < THRESHOLD
            assert abs(float(r["routing_continuity_pct"])) < THRESHOLD
    log = read_json("swmm_run_log.json")
    tide_runs = [r for r in log["runs"] if r["name"].startswith("tide:")]
    assert len(tide_runs) == read_json("tide_summary.json")["n_tide_runs"] > 100


def test_sweep_is_monotone_and_has_a_threshold(summ, inputs):
    rows = read_csv("tide_level_sweep.csv")
    lv = [float(r["hw_minus_outfall_ground_m"]) for r in rows]
    assert lv == sorted(lv) and lv[0] == inputs["settings"]["sweep_min"] and lv[-1] == 0.0
    for key in ("d_flood_m3_open", "d_flood_m3_gated", "gvf_extent_main_m", "gvf_n_fail_due_to_tide"):
        v = [float(r[key]) for r in rows]
        assert all(b >= a for a, b in zip(v, v[1:])), key
    # nothing happens below the outfall invert
    inv_rel = inputs["datum"]["outfall_invert_shd"] - inputs["datum"]["outfall_ground_shd"]
    for r, x in zip(rows, lv):
        if x < inv_rel:
            assert float(r["d_flood_m3_open"]) == 0 and float(r["gvf_max_rise_m"]) == 0
    # the steady check fails first just above the critical outfall level
    crit = -summ["design_tw_crit_below_ground_m"]
    first_fail = next(x for r, x in zip(rows, lv) if int(r["gvf_n_fail_due_to_tide"]) > 0)
    assert crit < first_fail <= crit + 0.05 + 1e-9
    assert summ["sweep_at_ground"] == {**summ["sweep_at_ground"], "hw_minus_outfall_ground_m": 0.0}
    assert summ["sweep_max_open_gated_diff_m3"] == max(
        abs(float(r["d_flood_m3_open"]) - float(r["d_flood_m3_gated"])) for r in rows)


def test_minimum_outfall_ground_arithmetic(summ, inputs):
    hw_now = inputs["datum"]["hw_now_shd"]
    depth = summ["design_tw_crit_below_ground_m"]
    first = summ["sweep_first_swmm_rise_hw_minus_ground_m"]
    last_ok = summ["sweep_last_no_swmm_rise_hw_minus_ground_m"]
    assert last_ok < first <= last_ok + summ["sweep_step_near_ground_m"] + 1e-9
    rows = read_csv("tide_level_sweep.csv")
    tol = inputs["settings"]["swmm_rise_tol_m"]
    for r in rows:                                   # no rise at or below last_ok, a rise at first
        lv = float(r["hw_minus_outfall_ground_m"])
        if lv <= last_ok + 1e-9:
            assert float(r["max_head_rise_m_open"]) < tol
        if abs(lv - first) < 1e-9:
            assert float(r["max_head_rise_m_open"]) >= tol
    for m, sc in zip(summ["min_outfall_ground"], coastal.SLR_SCENARIOS):
        assert m["slr_id"] == sc["id"]
        assert m["hw_shd"] == pytest.approx(hw_now + sc["rise_m"], abs=1e-3)
        assert m["min_outfall_ground_shd_cop_freeboard"] == pytest.approx(m["hw_shd"] + depth, abs=0.006)
        assert m["min_outfall_ground_shd_swmm_no_rise"] == pytest.approx(m["hw_shd"] - last_ok, abs=0.006)
        assert m["margin_at_cop_platform_level_m"] == pytest.approx(
            coastal.MIN_PLATFORM_LEVEL_SHD["southern_coast"] - m["min_outfall_ground_shd_cop_freeboard"],
            abs=0.011)
    assert summ["design_tw_crit_shd"] == pytest.approx(
        coastal.local_to_shd(summ["design_tw_crit_local"], inputs["datum"]["outfall_ground_local"]), abs=1e-3)


def test_critical_levels_per_storm(net, summ, secs):
    by = summ["critical_tailwater_by_tag"]
    assert by["design_10yr_design"]["tw_crit_shd"] == summ["design_tw_crit_shd"]
    for tag, c in by.items():
        # design sizes under a heavier storm already fail without any tide
        if tag.endswith("_design") and tag != "design_10yr_design":
            assert c["tw_crit_shd"] is None
        else:
            assert c["tw_crit_shd"] is not None
            assert float(c["outfall_invert_shd"]) < c["tw_crit_shd"] < summ["design_tw_crit_shd"] + 1e-9


def test_upsizing_results_match_a_rerun(net, secs, design, summ, inputs):
    flows = {r.reach: r.q_m3s for r in design}
    g_loc = inputs["datum"]["outfall_ground_local"]
    assert summ["upsizing_under_tailwater"], "the sweep must reach levels that cost freeboard"
    for u in summ["upsizing_under_tailwater"]:
        tw = g_loc + u["hw_minus_outfall_ground_m"]
        prof = bw.network_profile(net, secs, rational.inverts(net, secs), flows, tw)
        free = bw.network_profile(net, secs, rational.inverts(net, secs), flows, None)
        assert sorted(set(bw.freeboard_failures(prof)) - set(bw.freeboard_failures(free))) == \
            u["fail_due_to_tide"]
        assert u["status"] == "infeasible" and "M4" in u["infeasible_reaches"]
        again = bw.upsize_for_tailwater(net, secs, flows, tw)
        assert again["status"] == u["status"]
        assert again["infeasible_reaches"] == u["infeasible_reaches"]
        assert u["changed"] == [] and again["changed"] == {}


def test_committed_sweep_backwater_reproduces(net, secs, design, inputs):
    from sgdrain import tide_pipeline
    flows = {r.reach: r.q_m3s for r in design}
    g_loc = inputs["datum"]["outfall_ground_local"]
    main_len = sum(r.length for r in net.main_line())
    for r in read_csv("tide_level_sweep.csv"):
        g = tide_pipeline.gvf(net, secs, flows, g_loc + float(r["hw_minus_outfall_ground_m"]))
        assert g["gvf_extent_main_m"] == float(r["gvf_extent_main_m"])
        assert g["gvf_max_rise_m"] == float(r["gvf_max_rise_m"])
        assert ";".join(g["gvf_fail_due_to_tide"]) == r["gvf_fail_due_to_tide"]
        assert ";".join(g["gvf_raised_reaches"]) == r["gvf_raised_reaches"]
        assert g["gvf_extent_main_m"] < main_len
