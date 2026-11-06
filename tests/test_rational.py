import pytest

from sgdrain import cop, hydraulics as hy, idf, rational
from conftest import read_csv, read_json


def test_catchment_basics(net):
    assert net.total_area_ha == pytest.approx(12.6)
    assert len(net.reaches) == 11
    # each sub-catchment rectangle is inside the estate and they do not overlap
    rects = [s.rect for s in net.subcatchments]
    area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in rects)
    assert area == pytest.approx(420 * 300)
    for s in net.subcatchments:
        assert cop.OVERLAND_TIME_MIN <= s.overland_time_min <= cop.OVERLAND_TIME_MAX
        assert sum(s.fractions.values()) == pytest.approx(1.0)


def test_topological_order(net):
    seen = set()
    for r in net.reaches:
        for u in net.incoming(r.frm):
            assert u.id in seen
        seen.add(r.id)


def test_contributing_area_and_ca_accumulate(net, design):
    out = design[-1]
    assert net.nodes[out.to].outfall
    assert out.area_ha == pytest.approx(net.total_area_ha)
    assert out.sum_ca_ha == pytest.approx(sum(s.c * s.area_ha for s in net.subcatchments))
    by = {r.reach: r for r in design}
    for r in net.reaches:
        expect = sum(s.area_ha for s in net.subs_at(r.frm)) + sum(by[u.id].area_ha for u in net.incoming(r.frm))
        assert by[r.id].area_ha == pytest.approx(expect)


def test_design_flow_is_rational_formula_at_converged_tc(net, design, T):
    for r in design:
        i = idf.intensity(T, r.tc_min)
        assert r.intensity_mm_hr == pytest.approx(i, rel=1e-9)
        assert r.q_m3s == pytest.approx(r.sum_ca_ha * i / 360.0, rel=1e-9)
        assert r.q_m3s == pytest.approx(cop.rational_q(r.c_eq, i, r.area_ha), rel=1e-9)


def test_tc_iteration_converged(net, design):
    by = {r.reach: r for r in design}
    for r in design:
        assert r.converged and r.iterations < rational.MAX_ITER
        # independent re-check of the fixed point: tc = tc_up + L / V(section at Q(tc))
        v = hy.manning_v(r.width_m, hy.normal_depth(r.q_m3s, r.width_m, r.slope, rational.N_CONCRETE),
                         r.slope, rational.N_CONCRETE)
        assert r.tc_min == pytest.approx(r.tc_up_min + r.length_m / (60 * v), abs=1e-3)
        assert r.travel_min > 0
        # tc_up = max(local overland times, upstream tc)
        reach = net.reach(r.reach)
        cands = [s.overland_time_min for s in net.subs_at(reach.frm)] + \
                [by[u.id].tc_min for u in net.incoming(reach.frm)]
        assert r.tc_up_min == pytest.approx(max(cands))


def test_every_reach_meets_cop_criteria(design):
    for r in design:
        y = hy.normal_depth(r.q_m3s, r.width_m, r.slope, rational.N_CONCRETE)
        v = r.q_m3s / (r.width_m * y)
        assert y <= (1 - cop.FREEBOARD_FRACTION) * r.depth_m + 1e-9, r.reach
        assert cop.V_MIN - 1e-9 <= v <= cop.V_MAX_CONCRETE + 1e-9, r.reach
        assert hy.froude(v, y) <= cop.FROUDE_MAX + 1e-9, r.reach
        assert r.width_m >= cop.MIN_DRAIN_DIMENSION_M - 1e-9
        assert r.depth_m >= cop.MIN_DRAIN_DIMENSION_M - 1e-9
        assert r.utilisation <= 1.0 + 1e-9
        assert r.utilisation == pytest.approx(
            r.q_m3s / hy.manning_q(r.width_m, 0.85 * r.depth_m, r.slope, rational.N_CONCRETE), rel=1e-9)
        assert r.compliant


def test_chosen_section_is_smallest_compliant(design):
    for r in design:
        area = r.width_m * r.depth_m
        for b, d in rational.CATALOGUE:
            if b * d < area - 1e-9:
                assert not rational.check_section(r.q_m3s, b, d, r.slope).ok, (r.reach, b, d)


def test_check_mode_reproduces_design(net, design, secs, T):
    chk = rational.run(net, T, mode="check", fixed=secs)
    for a, b in zip(design, chk):
        assert b.q_m3s == pytest.approx(a.q_m3s, rel=1e-6)
        assert b.utilisation == pytest.approx(a.utilisation, rel=1e-6)
        assert b.compliant


def test_levels(net, secs):
    inv = rational.inverts(net, secs)
    for r in net.reaches:
        lv = inv[r.id]
        assert lv["cope_up"] <= net.nodes[r.frm].ground + 1e-9
        assert lv["cope_dn"] <= net.nodes[r.to].ground + 1e-9
        assert lv["inv_dn"] < lv["inv_up"]
        assert lv["inv_up"] - lv["inv_dn"] == pytest.approx(secs[r.id][2] * r.length)
        for u in net.incoming(r.frm):
            assert lv["inv_up"] <= inv[u.id]["inv_dn"] + 1e-9


def test_committed_design_table_reproduces(design):
    rows = read_csv("design_table.csv")
    assert [r["reach"] for r in rows] == [r.reach for r in design]
    for row, r in zip(rows, design):
        for k in ("q_m3s", "tc_min", "utilisation", "v_ms", "y_m"):
            assert float(row[k]) == pytest.approx(getattr(r, k), rel=1e-5)
        assert float(row["width_m"]) == r.width_m and float(row["depth_m"]) == r.depth_m
    s = read_json("design_summary.json")
    assert s["max_utilisation"] == round(max(r.utilisation for r in design), 3)
    assert s["all_compliant"] is True
