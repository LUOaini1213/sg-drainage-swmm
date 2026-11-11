"""Steady gradually varied flow (backwater) through the drain network.

The rational design checks every reach at normal depth.  When the tide holds
the outfall water level up, the water surface in the lower reaches follows a
backwater (M1) curve instead.  This module computes that curve at the
rational design flows to check the COP freeboard (Cl. 7.3.4: cope minus
water level of at least 15% of the drain depth) and to measure how far
upstream the tide is felt.

Method: the standard step method (see e.g. Chow, *Open-Channel Hydraulics*,
1959), energy balance between stations dx apart in a rectangular open drain,
Manning friction slope Sf = n^2 V^2 / R^(4/3) averaged over the step:

    z_u + y_u + V_u^2/2g = z_d + y_d + V_d^2/2g + (Sf_u + Sf_d)/2 * dx

Boundary of each reach, at its downstream end: the water level at its
downstream node, or normal depth if that is higher.  A tailwater below the
normal-depth level therefore leaves the design flow unchanged; the drawdown
towards a free outfall is ignored (conservative).  Junction losses are
ignored: the water level is continuous through a node.  Flows are constant
along a reach (sub-catchment inflow is lumped at the upstream node, as in the
rational design).
"""
from __future__ import annotations

import math

from . import cop, hydraulics as hy, rational

N = cop.MANNING_N["concrete"]
G = cop.G
DX_M = 1.0           # target station spacing (m)
RISE_TOL_M = 0.01    # "in backwater": level at least 1 cm above the normal-depth level


def velocity_head(q: float, b: float, y: float) -> float:
    v = q / (b * y)
    return v * v / (2.0 * G)


def friction_slope(q: float, b: float, y: float, n: float = N) -> float:
    a = b * y
    r = a / (b + 2.0 * y)
    v = q / a
    return (n * v) ** 2 / r ** (4.0 / 3.0)


def step_upstream(q: float, b: float, s0: float, dx: float, y_dn: float, n: float = N) -> float:
    """Depth at the station ``dx`` upstream of a station with depth ``y_dn``
    (subcritical solution of the energy balance; bisection, which is safe
    because the residual increases with depth above critical depth)."""
    h_dn = y_dn + velocity_head(q, b, y_dn)
    sf_dn = friction_slope(q, b, y_dn, n)

    def resid(y: float) -> float:
        return (s0 * dx + y + velocity_head(q, b, y) - h_dn
                - 0.5 * (friction_slope(q, b, y, n) + sf_dn) * dx)

    lo = hy.critical_depth(q, b)
    if resid(lo) > 0.0:      # no subcritical solution: the flow would choke
        return lo
    hi = max(y_dn, lo) + 1.0
    while resid(hi) <= 0.0:
        hi += 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if resid(mid) > 0.0:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-11:
            break
    return 0.5 * (lo + hi)


def reach_profile(q: float, b: float, d: float, s0: float, length: float, inv_dn: float,
                  y_dn: float, n: float = N, dx_target: float = DX_M) -> dict:
    """Water surface along one reach, stepping upstream from its downstream
    end.  ``x`` is the distance upstream of the downstream end."""
    nstep = max(1, math.ceil(length / dx_target - 1e-9))
    dx = length / nstep
    xs, ys = [0.0], [y_dn]
    for k in range(nstep):
        ys.append(step_upstream(q, b, s0, dx, ys[-1], n))
        xs.append((k + 1) * dx)
    yn = hy.normal_depth(q, b, s0, n)
    inv = [inv_dn + s0 * x for x in xs]
    wl = [z + y for z, y in zip(inv, ys)]
    rise = [w - (z + yn) for w, z in zip(wl, inv)]
    fb_limit = (1.0 - cop.FREEBOARD_FRACTION) * d
    return {
        "x": xs, "y": ys, "wl": wl, "inv": inv, "rise": rise, "yn": yn, "depth": d,
        "y_dn": ys[0], "y_up": ys[-1], "wl_dn": wl[0], "wl_up": wl[-1],
        "rise_dn": rise[0], "rise_up": rise[-1],
        "max_y_over_d": max(ys) / d,
        "freeboard_ok": all(y <= fb_limit + 1e-9 for y in ys),
        "overtops": any(y > d + 1e-9 for y in ys),
    }


def outfall_reach(net):
    return next(r for r in net.reaches if net.nodes[r.to].outfall)


def network_profile(net, secs: dict, inv: dict, flows: dict, tailwater: float | None,
                    n: float = N, dx_target: float = DX_M) -> dict:
    """Profiles of every reach for an outfall water level ``tailwater`` (local
    datum; None = free outfall).  Reaches are processed from the outfall
    upstream; each node takes the level at the upstream end of its outgoing
    reach (the network is a tree)."""
    wl_node: dict[str, float] = {}
    for nid, node in net.nodes.items():
        if node.outfall:
            wl_node[nid] = -math.inf if tailwater is None else tailwater
    out: dict[str, dict] = {}
    for r in reversed(net.reaches):
        if r.to not in wl_node:
            raise RuntimeError(f"{r.id}: downstream node {r.to} not processed yet")
        b, d, s = secs[r.id]
        q = flows[r.id]
        yn = hy.normal_depth(q, b, s, n)
        y_dn = max(yn, wl_node[r.to] - inv[r.id]["inv_dn"])
        p = reach_profile(q, b, d, s, r.length, inv[r.id]["inv_dn"], y_dn, n, dx_target)
        p["cope_dn"] = inv[r.id]["inv_dn"] + d
        p["cope_up"] = inv[r.id]["inv_up"] + d
        out[r.id] = p
        wl_node[r.frm] = p["wl_up"]
    return out


def tide_effect(net, prof: dict, prof_free: dict, tol: float = RISE_TOL_M) -> dict:
    """How far upstream the tide is felt: the rise of the water level over
    the free-outfall profile at the same flows (both profiles use the same
    stations).  Even with a free outfall a small reach can sit in the
    backwater of a deeper one at a junction; that part is not the tide's.

    ``main_m``: distance from the outfall, up the main drain, to the last
    station (continuous from the outfall) raised by at least ``tol``.
    ``reaches``: every reach raised by at least ``tol`` at its downstream end,
    with the length over which it is, and the rise there."""
    rise = {rid: [a - b for a, b in zip(prof[rid]["wl"], prof_free[rid]["wl"])] for rid in prof}
    main = list(reversed(net.main_line()))      # outfall first
    extent, chain = 0.0, 0.0
    for r in main:
        stop = False
        for x, dz in zip(prof[r.id]["x"], rise[r.id]):
            if dz >= tol:
                extent = chain + x
            else:
                stop = True
                break
        if stop:
            break
        chain += r.length
    reaches = {}
    for r in net.reaches:
        if rise[r.id][0] >= tol:
            reaches[r.id] = {
                "rise_dn_m": round(rise[r.id][0], 3),
                "length_m": round(max(x for x, dz in zip(prof[r.id]["x"], rise[r.id]) if dz >= tol), 1),
            }
    return {"main_m": round(extent, 1) if rise[main[0].id][0] >= tol else 0.0,
            "reaches": reaches,
            "max_rise_m": round(max(max(v) for v in rise.values()), 4)}


def freeboard_failures(prof: dict) -> list[str]:
    return [rid for rid, p in prof.items() if not p["freeboard_ok"]]


def critical_tailwater(net, secs: dict, inv: dict, flows: dict, tol: float = 1e-4) -> float | None:
    """Highest outfall water level at which every reach still keeps the COP
    freeboard at the given flows (None if a reach fails even with a free
    outfall).  Bisection: a higher tailwater never lowers any level."""
    def ok(tw):
        return not freeboard_failures(network_profile(net, secs, inv, flows, tw))
    r = outfall_reach(net)
    lo = inv[r.id]["inv_dn"]
    hi = inv[r.id]["cope_dn"]
    if not ok(lo):
        return None
    if ok(hi):
        return hi
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo


def upsize_for_tailwater(net, secs: dict, flows: dict, tailwater: float) -> dict:
    """Smallest catalogue enlargement, reach by reach from the outfall upstream
    (width and depth never reduced, gradient kept, normal-depth COP checks
    still met), that keeps the COP freeboard under the tailwater.  The cope
    stays at or below ground (rational.inverts), so a deeper drain sits lower:
    where the tide alone stands above cope - 15% of depth no enlargement
    helps, and the reach is reported as infeasible."""
    cur = dict(secs)
    infeasible = []
    done: list[str] = []
    for r in reversed(net.reaches):
        prof = network_profile(net, cur, rational.inverts(net, cur), flows, tailwater)
        done.append(r.id)
        if prof[r.id]["freeboard_ok"]:
            continue
        b0, d0, s0 = cur[r.id]
        chosen = None
        for bb, dd in rational.CATALOGUE:
            if bb < b0 - 1e-9 or dd < d0 - 1e-9 or bb * dd <= b0 * d0 + 1e-9:
                continue
            if not rational.check_section(flows[r.id], bb, dd, s0).ok:
                continue
            trial = dict(cur)
            trial[r.id] = (bb, dd, s0)
            p = network_profile(net, trial, rational.inverts(net, trial), flows, tailwater)
            if all(p[k]["freeboard_ok"] for k in done if k not in infeasible):
                chosen = (bb, dd, s0)
                break
        if chosen is None:
            infeasible.append(r.id)
        else:
            cur[r.id] = chosen
    final = network_profile(net, cur, rational.inverts(net, cur), flows, tailwater)
    changed = {k: {"from": f"{secs[k][0]:.1f} x {secs[k][1]:.1f}",
                   "to": f"{cur[k][0]:.1f} x {cur[k][1]:.1f}"}
               for k in cur if cur[k][:2] != secs[k][:2]}
    fails = freeboard_failures(final)
    status = ("no change needed" if not changed and not fails else
              "infeasible" if fails else "upsized")
    return {"status": status, "secs": cur, "changed": changed,
            "infeasible_reaches": sorted(set(infeasible) | set(fails))}
