"""Rational-method design and check of the drain network (COP Part II, Cl. 7).

For each reach, in upstream-to-downstream order:

* contributing area A and sum(C*A) = all sub-catchments upstream of the reach,
  each lumped at the upstream node of the reach it drains to (conservative);
* tc at the downstream end of the reach = max(overland time of sub-catchments
  at the upstream node, tc of incoming reaches) + travel time in the reach
  (Clause 7.1.4: tc = to + td);
* I = IDF(T, tc) (Clause 7.1.3 / Appendix 4) and Qr = C I A / 360 (Clause 7.1.1);
* the travel time depends on the velocity, which depends on the section chosen
  for Qr, so tc is iterated to a fixed point.

Section acceptance at the design flow (normal depth y in a rectangular
concrete U-drain, n from Clause 7.2.3):
  freeboard  y <= (1 - 0.15) D                 Clause 7.3.4
  velocity   1.0 <= V <= 3.0 m/s               Clauses 7.3.1, 7.3.2
  Froude     Fr <= 0.8                         Clause 7.3.3
  size       W, D >= 0.6 m                     Clause 4.3.1 (applied to all drains)

"Utilisation" = Qr / Qc where Qc is the Manning capacity with the water
surface at 0.85 D, i.e. the capacity that still leaves the COP freeboard.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from . import cop, hydraulics as hy, idf
from .network import Network, Reach

N_CONCRETE = cop.MANNING_N["concrete"]

# Size catalogue (assumption): internal width and depth on a 0.1 m grid.  The
# COP fixes only the 0.6 m minimum (Cl. 4.3.1); real projects would use the
# LTA standard drain details referenced in Cl. 9.1.2 / Drawing No. 1.
WIDTHS = [round(0.6 + 0.1 * k, 1) for k in range(25)]    # 0.6 .. 3.0 m
DEPTHS = [round(0.6 + 0.1 * k, 1) for k in range(15)]    # 0.6 .. 2.0 m
CATALOGUE = sorted(((b, d) for b in WIDTHS for d in DEPTHS),
                   key=lambda s: (s[0] * s[1], s[1], s[0]))

# Invert gradients tried when the ground slope admits no compliant section
# (assumption).  The ground slope is always tried first.
GRADIENT_OPTIONS = [1 / 150, 1 / 200, 1 / 250, 1 / 300, 1 / 350, 1 / 400,
                    1 / 500, 1 / 600, 1 / 800, 1 / 1000]

TC_TOL_MIN = 1e-4
MAX_ITER = 60


@dataclass
class SectionCheck:
    width: float
    depth: float
    slope: float
    q: float
    y: float
    v: float
    froude: float
    q_capacity: float
    utilisation: float
    freeboard_ok: bool
    vmin_ok: bool
    vmax_ok: bool
    froude_ok: bool

    @property
    def ok(self) -> bool:
        return self.freeboard_ok and self.vmin_ok and self.vmax_ok and self.froude_ok

    @property
    def ok_capacity(self) -> bool:
        return self.freeboard_ok


def check_section(q: float, b: float, d: float, s: float, n: float = N_CONCRETE) -> SectionCheck:
    y = hy.normal_depth(q, b, s, n)
    y_vel = min(y, d)           # if the drain overtops, velocity of the full section
    v = hy.manning_v(b, y_vel, s, n) if y_vel > 0 else 0.0
    fr = hy.froude(v, y_vel) if y_vel > 0 else 0.0
    qc = hy.capacity_with_freeboard(b, d, s, n, cop.FREEBOARD_FRACTION)
    return SectionCheck(
        width=b, depth=d, slope=s, q=q, y=y, v=v, froude=fr, q_capacity=qc,
        utilisation=q / qc,
        freeboard_ok=y <= (1.0 - cop.FREEBOARD_FRACTION) * d + 1e-12,
        vmin_ok=v >= cop.V_MIN - 1e-12,
        vmax_ok=v <= cop.V_MAX_CONCRETE + 1e-12,
        froude_ok=fr <= cop.FROUDE_MAX + 1e-12,
    )


def select_section(q: float, s: float, min_b: float = cop.MIN_DRAIN_DIMENSION_M,
                   min_d: float = cop.MIN_DRAIN_DIMENSION_M) -> SectionCheck | None:
    """Smallest catalogue section (by area) meeting every criterion."""
    for b, d in CATALOGUE:
        if b < min_b - 1e-9 or d < min_d - 1e-9:
            continue
        chk = check_section(q, b, d, s)
        if chk.ok:
            return chk
    return None


def gradient_preference(ground_slope: float) -> list[float]:
    others = sorted(GRADIENT_OPTIONS, key=lambda s: abs(math.log(s / ground_slope)))
    return [ground_slope] + others


@dataclass
class ReachResult:
    reach: str
    frm: str
    to: str
    length_m: float
    ground_slope: float
    slope: float
    gradient_from_ground: bool
    area_ha: float
    sum_ca_ha: float
    c_eq: float
    tc_up_min: float
    travel_min: float
    tc_min: float
    intensity_mm_hr: float
    q_m3s: float
    width_m: float
    depth_m: float
    y_m: float
    y_over_d: float
    v_ms: float
    froude: float
    q_capacity_m3s: float
    utilisation: float
    freeboard_ok: bool
    vmin_ok: bool
    vmax_ok: bool
    froude_ok: bool
    compliant: bool
    iterations: int
    converged: bool
    tc_residual_min: float


def _solve_reach(r: Reach, tc_up: float, sum_ca: float, T: int, uplift: float,
                 chooser) -> tuple[float, SectionCheck, float, int, bool, float]:
    """Fixed-point iteration on tc for one reach."""
    v = 1.5
    tc = tc_up + r.length / (60.0 * v)
    history: list[tuple[float, SectionCheck]] = []
    for it in range(1, MAX_ITER + 1):
        q = cop.rational_q(1.0, idf.intensity(T, tc, uplift), sum_ca)
        chk = chooser(q)
        tc_new = tc_up + r.length / (60.0 * max(chk.v, 1e-6))
        history.append((tc, chk))
        if abs(tc_new - tc) < TC_TOL_MIN:
            q = cop.rational_q(1.0, idf.intensity(T, tc_new, uplift), sum_ca)
            chk = chooser(q)
            return tc_new, chk, q, it, True, abs(tc_new - tc)
        # discrete sizes can make the iteration cycle between two sections:
        # resolve conservatively with the larger flow of the cycle and flag it
        if any(abs(tc_new - h[0]) < TC_TOL_MIN for h in history[:-1]):
            cyc = [h for h in history if h[0] >= min(tc_new, tc) - TC_TOL_MIN]
            tc_c = min(h[0] for h in cyc)
            q = cop.rational_q(1.0, idf.intensity(T, tc_c, uplift), sum_ca)
            chk = chooser(q)
            return tc_c, chk, q, it, False, abs(tc_new - tc)  # flagged: not a true fixed point
        tc = tc_new
    return tc, chk, q, MAX_ITER, False, abs(tc_new - tc)


def run(net: Network, T: int, uplift: float = 0.0, mode: str = "design",
        fixed: dict[str, tuple[float, float, float]] | None = None,
        overland_time_override: float | None = None) -> list[ReachResult]:
    """Design ('design'), check fixed sections ('check') or upsize fixed
    sections to compliance without shrinking them ('upsize').

    ``fixed`` maps reach id -> (width, depth, slope) for 'check'/'upsize'.
    """
    if mode not in ("design", "check", "upsize"):
        raise ValueError(mode)
    if mode != "design" and fixed is None:
        raise ValueError("fixed sections required")
    out: dict[str, ReachResult] = {}
    for r in net.reaches:
        local = net.subs_at(r.frm)
        to_times = [overland_time_override if overland_time_override is not None
                    else s.overland_time_min for s in local]
        tc_up = max(to_times + [out[u.id].tc_min for u in net.incoming(r.frm)])
        subs = net.contributing_subs(r.frm)
        area = sum(s.area_ha for s in subs)
        sum_ca = sum(s.c * s.area_ha for s in subs)

        if mode == "design":
            state = {}

            def chooser(q, r=r, state=state):
                for s in gradient_preference(r.ground_slope):
                    chk = select_section(q, s)
                    if chk is not None:
                        state["from_ground"] = (s == r.ground_slope)
                        return chk
                raise RuntimeError(f"{r.id}: no compliant section for Q={q:.3f}")
        elif mode == "check":
            b, d, s = fixed[r.id]
            state = {"from_ground": abs(s - r.ground_slope) < 1e-12}

            def chooser(q, b=b, d=d, s=s):
                return check_section(q, b, d, s)
        else:
            b0, d0, s0 = fixed[r.id]
            state = {"from_ground": abs(s0 - r.ground_slope) < 1e-12}

            def chooser(q, b0=b0, d0=d0, s0=s0):
                chk = select_section(q, s0, min_b=b0, min_d=d0)
                if chk is None:
                    raise RuntimeError(f"{r.id}: no compliant upsizing for Q={q:.3f}")
                return chk

        tc, chk, q, its, conv, resid = _solve_reach(r, tc_up, sum_ca, T, uplift, chooser)
        out[r.id] = ReachResult(
            reach=r.id, frm=r.frm, to=r.to, length_m=r.length,
            ground_slope=r.ground_slope, slope=chk.slope,
            gradient_from_ground=state["from_ground"],
            area_ha=area, sum_ca_ha=sum_ca, c_eq=sum_ca / area,
            tc_up_min=tc_up, travel_min=tc - tc_up, tc_min=tc,
            intensity_mm_hr=idf.intensity(T, tc, uplift), q_m3s=q,
            width_m=chk.width, depth_m=chk.depth, y_m=chk.y, y_over_d=chk.y / chk.depth,
            v_ms=chk.v, froude=chk.froude, q_capacity_m3s=chk.q_capacity,
            utilisation=chk.utilisation, freeboard_ok=chk.freeboard_ok,
            vmin_ok=chk.vmin_ok, vmax_ok=chk.vmax_ok, froude_ok=chk.froude_ok,
            compliant=chk.ok, iterations=its, converged=conv, tc_residual_min=resid,
        )
    return [out[r.id] for r in net.reaches]


def sections(results: list[ReachResult]) -> dict[str, tuple[float, float, float]]:
    return {r.reach: (r.width_m, r.depth_m, r.slope) for r in results}


def inverts(net: Network, secs: dict[str, tuple[float, float, float]]) -> dict[str, dict]:
    """Invert levels, top-down: cope (invert + D) at or below ground at both
    ends, and no reach starts higher than any drain flowing into it."""
    out: dict[str, dict] = {}
    for r in net.reaches:
        b, d, s = secs[r.id]
        g_up = net.nodes[r.frm].ground
        g_dn = net.nodes[r.to].ground
        inv_up = min(g_up - d, g_dn - d + s * r.length)
        for u in net.incoming(r.frm):
            inv_up = min(inv_up, out[u.id]["inv_dn"])
        inv_dn = inv_up - s * r.length
        out[r.id] = {"inv_up": inv_up, "inv_dn": inv_dn,
                     "cope_up": inv_up + d, "cope_dn": inv_dn + d}
    return out


def as_rows(results: list[ReachResult]) -> list[dict]:
    return [asdict(r) for r in results]
