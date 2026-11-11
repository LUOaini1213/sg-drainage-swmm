"""Tide and sea-level-rise stress test of the outfall: tailwater, backwater,
and screening-level responses.  Called from pipeline.main(); writes
results/tide_*.json|csv, two figures and a few .inp models.

What is run (all SWMM runs are logged in pipeline.RUN_LOG):

* Boundary: the outfall sea level follows the published tide predictions
  around the highest predicted high water of Nov-Dec 2026 (MPA via NEA),
  shifted by each sea-level-rise scenario (coastal.SLR_SCENARIOS), with high
  water placed at the centre of the storm's peak 5-min block (storm and high
  tide coincide: a conservative pairing, see README).  Open outfall (drains
  start filled to the tide level) and flap-gated outfall (drains start empty).
* Datum: catchment and tide are tied to SHD by assumptions A1 and A2
  (coastal.py); the sensitivity runs move the outfall ground level.
* Storms: the 10-yr design storm and the three stress storms, on the design
  sizes and (stress storms) on their minimum rational upsizing.
* Steady check: backwater curves at the rational flows (backwater.py) for
  the COP freeboard and the backwater extent.
* Responses: the highest outfall water level that keeps the COP freeboard,
  the minimum drain upsizing under tailwater, a flap gate, and a pump-sump
  trade-off with a SWMM check.
"""
from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path

from . import (backwater as bw, coastal, cop, hyetograph, pipeline, pumpsump, rational,
               swmm_model, tide)

RESULTS = pipeline.RESULTS
SIM_MIN = 60 * swmm_model.OPTIONS["sim_hours"]
TIDE_STEP_MIN = 5
SWMM_RISE_TOL_M = 0.02       # node "raised by the tide": max head up by 2 cm or more
SWEEP_LEVELS = ([round(-2.6 + 0.1 * k, 2) for k in range(13)] +
                [round(-1.3 + 0.05 * k, 2) for k in range(27)])   # HW minus outfall ground (m)
PUMP_FRACTIONS = [1.0, 0.9, 0.75, 0.6, 0.5]
VERIFY_PUMP_FRACTION = 0.75


# ----------------------------------------------------------------- helpers
def storm_peak_minute(hy: list[float], dt_min: int) -> float:
    """Centre of the peak block of a hyetograph (minutes from its start)."""
    k = hy.index(max(hy))
    return (k + 0.5) * dt_min


def design_peak_minute(net) -> float:
    hy = hyetograph.alternating_block(cop.design_return_period(net.total_area_ha),
                                      pipeline.STORM_DURATION_MIN, pipeline.STORM_DT_MIN)
    return storm_peak_minute(hy, pipeline.STORM_DT_MIN)


def tide_context(net) -> dict:
    # The committed extract: statistics of the full table, and the extremes around
    # its highest high water (the full table is not redistributed, see tide.py).
    ex = tide.load_extract()
    ev, st, mean_cd = ex.events, ex.stats, ex.mean_level_cd
    hw = tide.highest_high_water(ev)
    peak = design_peak_minute(net)
    curve = tide.aligned_curve(ev, hw, peak, SIM_MIN, TIDE_STEP_MIN)
    of = next(n for n in net.nodes.values() if n.outfall)
    return {"events": ev, "stats": st, "hw": hw, "mean_cd": mean_cd, "peak_min": peak,
            "curve_cd": curve, "of_id": of.id, "of_ground_local": of.ground}


def stage_series(ctx: dict, slr: float, outfall_ground_shd: float) -> list[tuple[float, float]]:
    """Sea level at the outfall (local datum) through the simulation."""
    return [(t, coastal.shd_to_local(coastal.cd_to_shd(h, ctx["mean_cd"]) + slr,
                                     ctx["of_ground_local"], outfall_ground_shd))
            for t, h in ctx["curve_cd"]]


def shifted_series(ctx: dict, hw_rel_ground: float) -> list[tuple[float, float]]:
    """Same tide curve, moved so that high water is ``hw_rel_ground`` above
    the outfall ground (a datum-free description of any datum/SLR pairing)."""
    top = max(h for _, h in ctx["curve_cd"])
    return [(t, ctx["of_ground_local"] + hw_rel_ground + (h - top)) for t, h in ctx["curve_cd"]]


def tidal_outfall(series: list[tuple[float, float]], gated: bool) -> dict:
    bc = {"type": "TIMESERIES", "series": series, "gated": gated}
    if not gated:
        bc["init_level"] = series[0][1]      # an open outfall lets the tide into the drains
    return bc


def run(net, secs, T, uplift, name, outfall, keep_model: bool = False):
    inv = rational.inverts(net, secs)
    hy = hyetograph.alternating_block(T, pipeline.STORM_DURATION_MIN, pipeline.STORM_DT_MIN, uplift)
    text = swmm_model.build_inp(net, secs, inv, hy, pipeline.STORM_DT_MIN,
                                f"sg-drainage-swmm tide/SLR {name}", outfall=outfall,
                                report_series=True)
    if keep_model:
        (RESULTS / "models").mkdir(parents=True, exist_ok=True)
        (RESULTS / "models" / f"{name}.inp").write_text(text)
    out_reach = bw.outfall_reach(net).id
    links = [out_reach] + (["PUMP1", "GATE"] if outfall and outfall.get("type") == "PUMPED" else [])
    tmp = Path(tempfile.mkdtemp(prefix="sgtide_"))
    try:
        p = tmp / f"{name}.inp"
        p.write_text(text)
        res, ser = swmm_model.run_inp_series(p, links=links, nodes=list(net.nodes))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    pipeline.RUN_LOG.append({"name": f"tide:{name}", "runoff": res.runoff_continuity_pct,
                             "routing": res.routing_continuity_pct})
    return res, ser


def main_nodes_from_outfall(net) -> list[tuple[str, float]]:
    out, ch = [], 0.0
    main = list(reversed(net.main_line()))
    out.append((main[0].to, 0.0))
    for r in main:
        ch += r.length
        out.append((r.frm, ch))
    return out


def compare(net, res, ser, res0, ser0) -> dict:
    """SWMM run with a tide boundary vs the same storm with a free outfall."""
    of = next(n for n, v in net.nodes.items() if v.outfall)
    head = {n: max(v) for n, v in ser["node_head"].items()}
    head0 = {n: max(v) for n, v in ser0["node_head"].items()}
    rise = {n: head[n] - head0[n] for n in head if n != of}
    flooded = sorted(n for n, v in res.nodes.items() if v["hours_flooded"] > 0)
    flooded0 = sorted(n for n, v in res0.nodes.items() if v["hours_flooded"] > 0)
    into_fb = [r.id for r in net.reaches if res.links[r.id]["max_over_full_depth"]
               > pipeline.SWMM_FREEBOARD_DEPTH_RATIO + 1e-9]
    into_fb0 = [r.id for r in net.reaches if res0.links[r.id]["max_over_full_depth"]
                > pipeline.SWMM_FREEBOARD_DEPTH_RATIO + 1e-9]
    extent_node, extent_m = None, 0.0
    for nid, ch in main_nodes_from_outfall(net)[1:]:
        if rise[nid] >= SWMM_RISE_TOL_M:
            extent_node, extent_m = nid, ch
        else:
            break
    return {
        "flood_m3": round(res.total_flood_volume_m3, 1),
        "d_flood_m3": round(res.total_flood_volume_m3 - res0.total_flood_volume_m3, 1),
        "flooded_nodes": flooded,
        "new_flooded_nodes": sorted(set(flooded) - set(flooded0)),
        "new_into_freeboard": sorted(set(into_fb) - set(into_fb0)),
        "max_head_rise_m": round(max(rise.values()), 3),
        "raised_nodes": sorted(n for n, v in rise.items() if v >= SWMM_RISE_TOL_M),
        "swmm_extent_node": extent_node,
        "swmm_extent_m": extent_m,
        "runoff_continuity_pct": res.runoff_continuity_pct,
        "routing_continuity_pct": res.routing_continuity_pct,
    }


def gvf(net, secs, flows, tw_local) -> dict:
    """Steady backwater check at the rational flows for a static outfall level."""
    inv = rational.inverts(net, secs)
    free = bw.network_profile(net, secs, inv, flows, None)
    prof = bw.network_profile(net, secs, inv, flows, tw_local)
    f0, f1 = set(bw.freeboard_failures(free)), set(bw.freeboard_failures(prof))
    eff = bw.tide_effect(net, prof, free)
    return {
        "gvf_fail_due_to_tide": sorted(f1 - f0),
        "gvf_fail_free": sorted(f0),
        "gvf_overtops": sorted(k for k, p in prof.items() if p["overtops"]),
        "gvf_extent_main_m": eff["main_m"],
        "gvf_raised_reaches": sorted(eff["reaches"]),
        "gvf_max_rise_m": eff["max_rise_m"],
        "outfall_y_over_d": round(prof[bw.outfall_reach(net).id]["y_dn"] /
                                  prof[bw.outfall_reach(net).id]["depth"], 3),
    }


def flows_of(rows) -> dict:
    return {r.reach: r.q_m3s for r in rows}


def write_rows(path: Path, rows: list[dict]) -> None:
    """CSV with the union of the rows' keys (rows that were not run have
    fewer fields); lists are joined with ';'."""
    keys: list[str] = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    flat = [{k: (";".join(r[k]) if isinstance(r.get(k), list) else r.get(k, "")) for k in keys}
            for r in rows]
    pipeline.write_csv(path, flat)


# -------------------------------------------------------------------- main
def main(net, design, secs, write_figures: bool = True) -> dict:
    ctx = tide_context(net)
    of_id, g_loc = ctx["of_id"], ctx["of_ground_local"]
    out_reach = bw.outfall_reach(net)
    inv_d = rational.inverts(net, secs)
    hw_shd_now = coastal.cd_to_shd(ctx["hw"].height_cd, ctx["mean_cd"])
    T_design = cop.design_return_period(net.total_area_ha)

    # storm x size sets ------------------------------------------------
    cases = [{"storm": "design_10yr", "label": f"{T_design}-yr design storm", "T": T_design,
              "uplift": 0.0, "sizes": "design", "secs": dict(secs)}]
    for key, sc in pipeline.STRESS_SCENARIOS.items():
        up = rational.run(net, sc["T"], sc["uplift"], mode="upsize", fixed=secs)
        cases.append({"storm": key, "label": sc["label"], "T": sc["T"], "uplift": sc["uplift"],
                      "sizes": "design", "secs": dict(secs)})
        cases.append({"storm": key, "label": sc["label"], "T": sc["T"], "uplift": sc["uplift"],
                      "sizes": "rational upsizing", "secs": rational.sections(up)})
    for c in cases:
        chk = rational.run(net, c["T"], c["uplift"], mode="check", fixed=c["secs"])
        c["flows"] = flows_of(chk)
        c["tag"] = f"{c['storm']}_{'design' if c['sizes'] == 'design' else 'upsized'}"
        c["free"] = run(net, c["secs"], c["T"], c["uplift"], f"{c['tag']}_free", None)
        inv_c = rational.inverts(net, c["secs"])
        c["inv_out"] = inv_c[out_reach.id]["inv_dn"]
        c["tw_crit"] = bw.critical_tailwater(net, c["secs"], inv_c, c["flows"])

    # scenario runs at the base datum ------------------------------------
    rows = []
    base_g = coastal.OUTFALL_GROUND_SHD_BASE
    for c in cases:
        for sc in coastal.SLR_SCENARIOS:
            series = stage_series(ctx, sc["rise_m"], base_g)
            peak = max(z for _, z in series)
            inv_c = rational.inverts(net, c["secs"])
            base = {"storm": c["storm"], "storm_label": c["label"], "sizes": c["sizes"],
                    "slr_id": sc["id"], "slr_m": sc["rise_m"], "outfall_ground_shd": base_g,
                    "peak_sea_level_local": round(peak, 3),
                    "peak_sea_level_shd": round(coastal.local_to_shd(peak, g_loc, base_g), 3),
                    "peak_above_outfall_invert_m": round(peak - c["inv_out"], 3),
                    "peak_below_outfall_ground_m": round(g_loc - peak, 3),
                    "reaches_below_high_water": [r.id for r in net.reaches
                                                 if inv_c[r.id]["inv_dn"] < peak]}
            above = peak > g_loc + 1e-9
            g = {} if above else gvf(net, c["secs"], c["flows"], peak)
            for gated in (False, True):
                row = dict(base, gated=gated, **g)
                if above:
                    row.update(status="sea above outfall ground")
                else:
                    keep = (c["tag"] == "design_10yr_design" and sc["id"] == "cpcop_2p15")
                    res, ser = run(net, c["secs"], c["T"], c["uplift"],
                                   f"tide_{c['tag']}_{sc['id']}_{'gated' if gated else 'open'}",
                                   tidal_outfall(series, gated), keep_model=keep)
                    row.update(status="run", **compare(net, res, ser, *c["free"]))
                rows.append(row)

    # datum sensitivity (design storm, design sizes) ----------------------
    dcase = cases[0]
    sens = []
    for g_shd in coastal.OUTFALL_GROUND_SHD_SENSITIVITY:
        for sc in coastal.SLR_SCENARIOS:
            series = stage_series(ctx, sc["rise_m"], g_shd)
            peak = max(z for _, z in series)
            row = {"outfall_ground_shd": g_shd, "slr_id": sc["id"], "slr_m": sc["rise_m"],
                   "peak_sea_level_shd": round(coastal.local_to_shd(peak, g_loc, g_shd), 3),
                   "peak_above_outfall_invert_m": round(peak - dcase["inv_out"], 3),
                   "peak_below_outfall_ground_m": round(g_loc - peak, 3)}
            if peak > g_loc + 1e-9:
                row["status"] = "sea above outfall ground"
            else:
                row.update(status="run", **gvf(net, secs, dcase["flows"], peak))
                for gated in (False, True):
                    res, ser = run(net, secs, T_design, 0.0,
                                   f"datum_g{g_shd:.1f}_{sc['id']}_{'gated' if gated else 'open'}",
                                   tidal_outfall(series, gated))
                    cmp_ = compare(net, res, ser, *dcase["free"])
                    sfx = "gated" if gated else "open"
                    row[f"d_flood_m3_{sfx}"] = cmp_["d_flood_m3"]
                    row[f"swmm_extent_m_{sfx}"] = cmp_["swmm_extent_m"]
                    row[f"max_head_rise_m_{sfx}"] = cmp_["max_head_rise_m"]
                    row[f"new_flooded_nodes_{sfx}"] = ";".join(cmp_["new_flooded_nodes"])
            sens.append(row)

    # level sweep: HW relative to outfall ground --------------------------
    sweep = []
    for lvl in SWEEP_LEVELS:
        series = shifted_series(ctx, lvl)
        peak = max(z for _, z in series)
        g = gvf(net, secs, dcase["flows"], peak)
        row = {"hw_minus_outfall_ground_m": lvl, "hw_local": round(peak, 3),
               "hw_shd_at_base_datum": round(coastal.local_to_shd(peak, g_loc), 3),
               "gvf_n_fail_due_to_tide": len(g["gvf_fail_due_to_tide"]),
               "gvf_fail_due_to_tide": g["gvf_fail_due_to_tide"],
               "gvf_raised_reaches": g["gvf_raised_reaches"],
               "gvf_extent_main_m": g["gvf_extent_main_m"], "gvf_max_rise_m": g["gvf_max_rise_m"]}
        if g["gvf_fail_due_to_tide"]:
            u = bw.upsize_for_tailwater(net, secs, dcase["flows"], peak)
            row.update(upsize_status=u["status"], upsize_infeasible=u["infeasible_reaches"],
                       upsize_changed=[f"{k} {v['from']}->{v['to']}" for k, v in u["changed"].items()])
        for gated in (False, True):
            res, ser = run(net, secs, T_design, 0.0,
                           f"sweep_{lvl:+.2f}_{'gated' if gated else 'open'}",
                           tidal_outfall(series, gated))
            cmp_ = compare(net, res, ser, *dcase["free"])
            sfx = "gated" if gated else "open"
            row[f"d_flood_m3_{sfx}"] = cmp_["d_flood_m3"]
            row[f"max_head_rise_m_{sfx}"] = cmp_["max_head_rise_m"]
            row[f"swmm_extent_m_{sfx}"] = cmp_["swmm_extent_m"]
            row[f"raised_nodes_{sfx}"] = cmp_["raised_nodes"]
        sweep.append(row)
    first_swmm = next((r["hw_minus_outfall_ground_m"] for r in sweep
                       if r["max_head_rise_m_open"] >= SWMM_RISE_TOL_M), None)
    first_gvf = next((r["hw_minus_outfall_ground_m"] for r in sweep
                      if r["gvf_max_rise_m"] >= bw.RISE_TOL_M), None)
    # highest sweep level at and below which SWMM shows no rise (safe side of the step)
    last_no_rise = (None if first_swmm is None else
                    max(r["hw_minus_outfall_ground_m"] for r in sweep
                        if r["hw_minus_outfall_ground_m"] < first_swmm))

    # responses ------------------------------------------------------------
    tw_crit = dcase["tw_crit"]
    depth_crit = g_loc - tw_crit                       # how far below ground the sea may stand
    min_ground = []
    for sc in coastal.SLR_SCENARIOS:
        hw_shd = hw_shd_now + sc["rise_m"]
        min_ground.append({
            "slr_id": sc["id"], "slr_m": sc["rise_m"], "hw_shd": round(hw_shd, 3),
            "min_outfall_ground_shd_cop_freeboard": round(hw_shd + depth_crit, 2),
            "min_outfall_ground_shd_swmm_no_rise": (None if last_no_rise is None else
                                                    round(hw_shd - last_no_rise, 2)),
            "margin_at_cop_platform_level_m": round(base_g - (hw_shd + depth_crit), 2),
        })
    # drain upsizing under tailwater: every sweep level at which the tide costs freeboard
    upsizing = [{"hw_minus_outfall_ground_m": r["hw_minus_outfall_ground_m"],
                 "hw_shd_at_base_datum": r["hw_shd_at_base_datum"],
                 "fail_due_to_tide": r["gvf_fail_due_to_tide"], "status": r["upsize_status"],
                 "infeasible_reaches": r["upsize_infeasible"], "changed": r["upsize_changed"]}
                for r in sweep if r["gvf_fail_due_to_tide"]]
    crit_cases = [{"storm": c["storm"], "sizes": c["sizes"],
                   "outfall_section": "{:.1f} x {:.1f}".format(*c["secs"][out_reach.id][:2]),
                   "outfall_invert_shd": round(coastal.local_to_shd(c["inv_out"], g_loc), 3),
                   "tw_crit_local": None if c["tw_crit"] is None else round(c["tw_crit"], 3),
                   "tw_crit_shd": (None if c["tw_crit"] is None else
                                   round(coastal.local_to_shd(c["tw_crit"], g_loc), 3)),
                   "slr_headroom_m": (None if c["tw_crit"] is None else
                                      round(coastal.local_to_shd(c["tw_crit"], g_loc) - hw_shd_now, 2))}
                  for c in cases]

    # pump-sump: gate shut for the whole storm, sea held at outfall ground --
    area_m2 = net.total_area_ha * 10_000
    pump = {"cop_cl_10_1_reference_m3s": round(coastal.cop_pump_capacity_m3s(area_m2), 3),
            "rational_outfall_q_m3s": round(design[-1].q_m3s, 3), "storms": {}}
    inflow_rows = None
    for c in cases:
        res0, ser0 = c["free"]
        t = [0.0] + ser0["t_s"]
        # the same rounded values that go into results/tide_outfall_inflow.csv
        q = [0.0] + [round(x, 4) for x in ser0["link_flow"][out_reach.id]]
        if inflow_rows is None:
            inflow_rows = [{"t_s": tt} for tt in t]
        for r_, qq in zip(inflow_rows, q):
            r_[c["tag"]] = round(qq, 4)
        entry = {"peak_inflow_m3s": round(max(q), 3), "event_volume_m3": round(pumpsump.volume(t, q), 1),
                 "trade_off": pumpsump.trade_off(t, q, PUMP_FRACTIONS)}
        if c["tag"] == "design_10yr_design":
            qp = VERIFY_PUMP_FRACTION * max(q)
            v = pumpsump.storage_required(t, q, qp)
            h_free = max(ser0["node_head"][of_id]) - c["inv_out"]
            area = v / h_free
            closed = run(net, c["secs"], c["T"], c["uplift"], "pump_check_gate_shut_no_pump",
                         {"type": "FIXED", "stage": g_loc, "gated": True})
            pumped = run(net, c["secs"], c["T"], c["uplift"], "pump_check_gate_shut_pumped",
                         {"type": "PUMPED", "stage": g_loc, "pump_m3s": qp, "sump_area_m2": area},
                         keep_model=True)
            entry["verification"] = {
                "sea_level_local": g_loc, "pump_m3s": round(qp, 3), "storage_m3": round(v, 1),
                "sump_area_m2": round(area, 1), "sump_depth_m": round(h_free, 3),
                "free_flood_m3": round(res0.total_flood_volume_m3, 1),
                "gate_shut_no_pump": compare(net, *closed, *c["free"]),
                "gate_shut_pumped": compare(net, *pumped, *c["free"]),
                "pumped_max_pump_flow_m3s": round(max(pumped[1]["link_flow"]["PUMP1"]), 3),
                "pumped_max_gate_flow_m3s": round(max(pumped[1]["link_flow"]["GATE"]), 4),
                "pumped_max_sump_level_local": round(max(pumped[1]["node_head"][of_id]), 3),
            }
        pump["storms"][c["tag"]] = entry
    pipeline.write_csv(RESULTS / "tide_outfall_inflow.csv", inflow_rows)

    # write ------------------------------------------------------------------
    inputs = {
        "tide": {**ctx["stats"], "peak_minute_in_storm": ctx["peak_min"],
                 "hw_used_cd": ctx["hw"].height_cd,
                 "hw_used_time": ctx["hw"].time.isoformat(timespec="minutes"),
                 "hw_used_time_text": ctx["hw"].time.strftime("%Y-%m-%d %H:%M"),
                 "hw_above_mean_m": round(ctx["hw"].height_cd - ctx["mean_cd"], 3),
                 "mean_hw_above_mean_m": round(ctx["stats"]["mean_hw_cd"] - ctx["mean_cd"], 3),
                 "tide_step_min": TIDE_STEP_MIN, "sim_min": SIM_MIN},
        "coastal": coastal.as_dict(),
        "datum": {"outfall_node": of_id, "outfall_ground_local": g_loc,
                  "outfall_ground_shd": base_g,
                  "local_minus_shd_m": round(g_loc - base_g, 3),
                  "outfall_invert_local": round(inv_d[out_reach.id]["inv_dn"], 3),
                  "outfall_invert_shd": round(coastal.local_to_shd(inv_d[out_reach.id]["inv_dn"], g_loc), 3),
                  "outfall_drain_depth_m": secs[out_reach.id][1],
                  "outfall_freeboard_line_shd": round(coastal.local_to_shd(
                      inv_d[out_reach.id]["cope_dn"] - cop.FREEBOARD_FRACTION * secs[out_reach.id][1], g_loc), 3),
                  "ground_min_shd": round(min(coastal.local_to_shd(n.ground, g_loc)
                                              for n in net.nodes.values()), 3),
                  "ground_max_shd": round(max(coastal.local_to_shd(n.ground, g_loc)
                                              for n in net.nodes.values()), 3),
                  "hw_now_shd": round(hw_shd_now, 3),
                  "combined_extreme_shd": round(coastal.TIDE_MEAN_SHD +
                                                coastal.COMBINED_EXTREME_ABOVE_MSL_M, 3),
                  "n_nodes": len(net.nodes),
                  "n_nodes_ground_below_combined_extreme": sum(
                      1 for n in net.nodes.values()
                      if coastal.local_to_shd(n.ground, g_loc) < coastal.TIDE_MEAN_SHD
                      + coastal.COMBINED_EXTREME_ABOVE_MSL_M)},
        "settings": {"swmm_rise_tol_m": SWMM_RISE_TOL_M, "gvf_rise_tol_m": bw.RISE_TOL_M,
                     "tide_resolution_m": tide.HEIGHT_RESOLUTION_M,
                     "gvf_dx_m": bw.DX_M, "sweep_min": SWEEP_LEVELS[0], "sweep_max": SWEEP_LEVELS[-1],
                     "pump_fractions": PUMP_FRACTIONS, "verify_pump_fraction": VERIFY_PUMP_FRACTION},
    }
    pipeline.write_json(RESULTS / "tide_inputs.json", inputs)
    write_rows(RESULTS / "tide_scenarios.csv", rows)
    write_rows(RESULTS / "tide_datum_sensitivity.csv", sens)
    write_rows(RESULTS / "tide_level_sweep.csv", sweep)

    def pick(storm, sizes, slr_id, gated):
        return next(r for r in rows if r["storm"] == storm and r["sizes"] == sizes
                    and r["slr_id"] == slr_id and r["gated"] == gated)

    ran = [r for r in rows if r["status"] == "run"]
    biggest = max(ran, key=lambda r: abs(r["d_flood_m3"]))
    summary = {
        "n_tide_runs": sum(1 for r in pipeline.RUN_LOG if r["name"].startswith("tide:")),
        "critical_tailwater": crit_cases,
        "critical_tailwater_by_tag": {c["tag"]: crit for c, crit in zip(cases, crit_cases)},
        "base_n_runs": len(ran),
        "base_largest_d_flood": {k: biggest[k] for k in ("storm", "storm_label", "sizes", "slr_id",
                                                         "gated", "d_flood_m3", "max_head_rise_m")},
        "base_n_sea_above_ground": sum(1 for r in rows if r["status"] != "run"),
        "base_max_gvf_extent_m": max(r["gvf_extent_main_m"] for r in ran),
        "base_max_swmm_extent_m": max(r["swmm_extent_m"] for r in ran),
        "base_max_head_rise_m": max(r["max_head_rise_m"] for r in ran),
        "design_tw_crit_local": round(tw_crit, 3),
        "design_tw_crit_shd": round(coastal.local_to_shd(tw_crit, g_loc), 3),
        "design_tw_crit_below_ground_m": round(depth_crit, 3),
        "design_slr_headroom_m": round(coastal.local_to_shd(tw_crit, g_loc) - hw_shd_now, 2),
        "min_outfall_ground": min_ground,
        "sweep_first_swmm_rise_hw_minus_ground_m": first_swmm,
        "sweep_last_no_swmm_rise_hw_minus_ground_m": last_no_rise,
        "sweep_step_near_ground_m": round(SWEEP_LEVELS[-1] - SWEEP_LEVELS[-2], 2),
        "sweep_first_gvf_rise_hw_minus_ground_m": first_gvf,
        "sweep_at_ground": {k: v for k, v in sweep[-1].items()},
        "sweep_max_open_gated_diff_m3": round(max(abs(r["d_flood_m3_open"] - r["d_flood_m3_gated"])
                                                  for r in sweep), 1),
        "base_design": {sc["id"]: {"open": pick("design_10yr", "design", sc["id"], False),
                                   "gated": pick("design_10yr", "design", sc["id"], True)}
                        for sc in coastal.SLR_SCENARIOS},
        "upsizing_under_tailwater": upsizing,
        "pump": pump,
    }
    pipeline.write_json(RESULTS / "tide_summary.json", summary)

    if write_figures:
        from . import plots
        flows_d = dcase["flows"]
        profiles = {
            "free": bw.network_profile(net, secs, inv_d, flows_d, None),
            "critical": bw.network_profile(net, secs, inv_d, flows_d, tw_crit),
            "at_ground": bw.network_profile(net, secs, inv_d, flows_d, g_loc),
        }
        base_open = [r for r in rows if r["storm"] == "design_10yr" and not r["gated"]]
        plots.tide_figures(net, secs, inv_d, profiles, base_open, sweep, summary, inputs,
                           RESULTS / "figures")
    return summary
