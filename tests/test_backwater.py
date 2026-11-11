"""Steady backwater (standard step) and the checks built on it."""
import math

import pytest

from sgdrain import backwater as bw, cop, hydraulics as hy, rational
from conftest import read_json

N = bw.N
G = cop.G


@pytest.fixture(scope="module")
def setup(net, design, secs):
    inv = rational.inverts(net, secs)
    flows = {r.reach: r.q_m3s for r in design}
    free = bw.network_profile(net, secs, inv, flows, None)
    return inv, flows, free


def _rk4_profile(q, b, s0, y0, length, n_steps):
    """Independent check: integrate dy/dx = -(S0 - Sf) / (1 - Fr^2) upstream
    (x measured upstream) with classical RK4."""
    def f(y):
        a = b * y
        v = q / a
        r = a / (b + 2 * y)
        sf = (N * v) ** 2 / r ** (4 / 3)
        fr2 = v * v / (G * y)
        return -(s0 - sf) / (1 - fr2)
    h = length / n_steps
    ys = [y0]
    for _ in range(n_steps):
        y = ys[-1]
        k1 = f(y)
        k2 = f(y + 0.5 * h * k1)
        k3 = f(y + 0.5 * h * k2)
        k4 = f(y + h * k3)
        ys.append(y + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6)
    return ys


def test_uniform_flow_is_reproduced():
    q, b, s = 1.3, 1.1, 1 / 300
    yn = hy.normal_depth(q, b, s, N)
    p = bw.reach_profile(q, b, 1.0, s, 120.0, 5.0, yn)
    assert max(abs(y - yn) for y in p["y"]) < 1e-6
    assert p["wl"][-1] - p["wl"][0] == pytest.approx(s * 120.0, abs=1e-6)


@pytest.mark.parametrize("q,b,s0,dy", [(2.0, 1.2, 1 / 300, 0.3), (0.8, 0.8, 1 / 200, 0.15),
                                       (4.6, 1.9, 1 / 300, 0.19)])
def test_m1_curve_against_independent_integration(q, b, s0, dy):
    yn = hy.normal_depth(q, b, s0, N)
    y0 = yn + dy
    p = bw.reach_profile(q, b, 2.0, s0, 150.0, 0.0, y0, dx_target=1.0)
    ref = _rk4_profile(q, b, s0, y0, 150.0, 1500)
    for k, y in enumerate(p["y"]):
        assert y == pytest.approx(ref[10 * k], abs=2e-4)
    ys = p["y"]
    assert all(b2 < a for a, b2 in zip(ys, ys[1:]))           # depth falls upstream on an M1 curve
    assert all(y > yn for y in ys)                             # ... and stays above normal depth
    assert ys[-1] - yn < dy                                    # ... approaching it


def test_energy_balance_holds_at_every_step():
    q, b, s0 = 2.0, 1.2, 1 / 300
    p = bw.reach_profile(q, b, 2.0, s0, 60.0, 7.0, hy.normal_depth(q, b, s0, N) + 0.4)
    for k in range(1, len(p["x"])):
        dx = p["x"][k] - p["x"][k - 1]
        h_up = p["inv"][k] + p["y"][k] + bw.velocity_head(q, b, p["y"][k])
        h_dn = p["inv"][k - 1] + p["y"][k - 1] + bw.velocity_head(q, b, p["y"][k - 1])
        sf = 0.5 * (bw.friction_slope(q, b, p["y"][k]) + bw.friction_slope(q, b, p["y"][k - 1]))
        assert h_up - h_dn - sf * dx == pytest.approx(0.0, abs=1e-9)


def test_friction_slope_is_manning():
    q, b, y = 1.5, 1.0, 0.6
    a, r = b * y, b * y / (b + 2 * y)
    assert bw.friction_slope(q, b, y) == pytest.approx((q / a) ** 2 * N ** 2 / r ** (4 / 3), rel=1e-12)
    # at normal depth the friction slope equals the bed slope
    s = 1 / 250
    assert bw.friction_slope(q, b, hy.normal_depth(q, b, s, N)) == pytest.approx(s, rel=1e-6)


def test_free_outfall_profile_keeps_the_design_compliant(net, setup):
    inv, flows, free = setup
    out = bw.outfall_reach(net).id
    for rid, p in free.items():
        assert p["y_dn"] >= p["yn"] - 1e-9
        assert p["freeboard_ok"] and not p["overtops"], rid
    assert free[out]["y_dn"] == pytest.approx(free[out]["yn"], abs=1e-12)
    # at a junction a smaller reach can sit in the backwater of a deeper one even
    # with a free outfall (C1 enters C2 at the same invert with less flow)
    assert free["C1"]["y_dn"] > free["C1"]["yn"] + 0.01
    eff = bw.tide_effect(net, free, free)
    assert eff["main_m"] == 0.0 and eff["reaches"] == {} and eff["max_rise_m"] == 0.0


def test_junction_levels_are_continuous(net, secs, setup):
    inv, flows, _ = setup
    prof = bw.network_profile(net, secs, inv, flows, inv["M4"]["cope_dn"] - 0.02)
    for r in net.reaches:
        for u in net.incoming(r.frm):
            # the incoming reach starts from the junction level, or its own normal depth if higher
            assert prof[u.id]["wl_dn"] == pytest.approx(
                max(prof[r.id]["wl_up"], inv[u.id]["inv_dn"] + prof[u.id]["yn"]), abs=1e-9)


def test_tailwater_below_the_normal_level_changes_nothing(net, secs, setup):
    inv, flows, free = setup
    out = bw.outfall_reach(net).id
    tw = inv[out]["inv_dn"] + free[out]["yn"] - 0.005
    prof = bw.network_profile(net, secs, inv, flows, tw)
    for rid in prof:
        assert prof[rid]["wl"] == free[rid]["wl"]
    eff = bw.tide_effect(net, prof, free)
    assert eff == {"main_m": 0.0, "reaches": {}, "max_rise_m": 0.0}


def test_higher_tailwater_raises_more_and_further(net, secs, setup):
    inv, flows, free = setup
    out = bw.outfall_reach(net).id
    tws = [inv[out]["cope_dn"] - k * 0.03 for k in range(6, -1, -1)]
    effects = [bw.tide_effect(net, bw.network_profile(net, secs, inv, flows, tw), free) for tw in tws]
    rises = [e["max_rise_m"] for e in effects]
    exts = [e["main_m"] for e in effects]
    assert all(b > a for a, b in zip(rises, rises[1:]))
    assert all(b >= a for a, b in zip(exts, exts[1:]))
    assert exts[-1] > net.reach(out).length                    # at cope level it passes J4
    # the rise at the outfall is the tailwater above the normal-depth level there
    p = bw.network_profile(net, secs, inv, flows, tws[-1])
    assert p[out]["wl_dn"] - free[out]["wl_dn"] == pytest.approx(
        tws[-1] - inv[out]["inv_dn"] - free[out]["yn"], abs=1e-9)


def test_tide_effect_counts_only_raised_stations(net, secs, setup):
    """Independent re-count of the backwater extent from the two profiles."""
    inv, flows, free = setup
    tol = bw.RISE_TOL_M
    for tw in (inv["M4"]["cope_dn"] - 0.15, inv["M4"]["cope_dn"] - 0.05, inv["M4"]["cope_dn"]):
        prof = bw.network_profile(net, secs, inv, flows, tw)
        eff = bw.tide_effect(net, prof, free)
        extent, chain, stop = 0.0, 0.0, False
        for r in reversed(net.main_line()):
            for x, a, b in zip(prof[r.id]["x"], prof[r.id]["wl"], free[r.id]["wl"]):
                if a - b >= tol:
                    extent = chain + x
                else:
                    stop = True
                    break
            if stop:
                break
            chain += r.length
        assert eff["main_m"] == pytest.approx(extent, abs=0.05)
        assert 0 < eff["main_m"] < sum(r.length for r in net.main_line())
        for rid, v in eff["reaches"].items():
            raised = [x for x, a, b in zip(prof[rid]["x"], prof[rid]["wl"], free[rid]["wl"]) if a - b >= tol]
            assert v["length_m"] == pytest.approx(max(raised), abs=0.05)
            assert v["length_m"] <= net.reach(rid).length
        for r in net.reaches:
            assert (r.id in eff["reaches"]) == (prof[r.id]["wl"][0] - free[r.id]["wl"][0] >= tol)


def test_critical_tailwater_is_bracketed(net, secs, setup):
    inv, flows, _ = setup
    tw = bw.critical_tailwater(net, secs, inv, flows)
    assert not bw.freeboard_failures(bw.network_profile(net, secs, inv, flows, tw - 1e-3))
    assert bw.freeboard_failures(bw.network_profile(net, secs, inv, flows, tw + 1e-3)) == ["M4"]
    # binding at the outfall end of M4: the freeboard line (cope - 15% of depth)
    d = secs["M4"][1]
    assert tw == pytest.approx(inv["M4"]["cope_dn"] - cop.FREEBOARD_FRACTION * d, abs=2e-4)
    s = read_json("tide_summary.json")
    assert s["design_tw_crit_local"] == round(tw, 3)


def test_critical_tailwater_none_when_failing_without_tide(net, secs, setup):
    inv, flows, _ = setup
    heavy = {k: 1.3 * v for k, v in flows.items()}
    assert bw.critical_tailwater(net, secs, inv, heavy) is None


def test_upsizing_cannot_beat_a_sea_above_the_freeboard_line(net, secs, setup):
    inv, flows, _ = setup
    tw = inv["M4"]["cope_dn"] - 0.10                     # above cope - 0.15 D = cope - 0.18
    u = bw.upsize_for_tailwater(net, secs, flows, tw)
    assert u["status"] == "infeasible" and "M4" in u["infeasible_reaches"]
    # nothing is enlarged when no enlargement helps (a trial must use the inverts of the
    # trial sections: with the old inverts a deeper drain's cope would rise above ground)
    assert u["changed"] == {} and u["secs"] == secs
    # independent check: no larger catalogue section for M4 keeps its downstream end
    # within the freeboard, because the cope stays at ground and the sea fixes the level
    b0, d0, s0 = secs["M4"]
    for bb, dd in rational.CATALOGUE:
        if bb >= b0 and dd >= d0:
            trial = dict(secs)
            trial["M4"] = (bb, dd, s0)
            p = bw.network_profile(net, trial, rational.inverts(net, trial), flows, tw)
            assert not p["M4"]["freeboard_ok"], (bb, dd)


def test_upsizing_not_needed_below_the_critical_level(net, secs, setup):
    inv, flows, _ = setup
    tw = bw.critical_tailwater(net, secs, inv, flows) - 0.01
    u = bw.upsize_for_tailwater(net, secs, flows, tw)
    assert u["status"] == "no change needed" and u["changed"] == {} and u["secs"] == secs


def test_upsizing_fixes_a_normal_depth_failure(net, secs, setup):
    inv, flows, _ = setup
    heavy = {k: 1.15 * v for k, v in flows.items()}
    low_tw = inv["M4"]["inv_dn"] - 1.0                  # the sea plays no part
    u = bw.upsize_for_tailwater(net, secs, heavy, low_tw)
    assert u["status"] == "upsized" and u["infeasible_reaches"] == []
    final = bw.network_profile(net, u["secs"], rational.inverts(net, u["secs"]), heavy, low_tw)
    assert not bw.freeboard_failures(final)
    for rid, (b, d, s) in u["secs"].items():
        b0, d0, s0 = secs[rid]
        assert b >= b0 and d >= d0 and s == s0
        assert rational.check_section(heavy[rid], b, d, s).ok
    assert set(u["changed"]) == {k for k in secs if u["secs"][k][:2] != secs[k][:2]}
