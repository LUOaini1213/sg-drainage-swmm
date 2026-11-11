"""End-to-end workflow: design -> SWMM check -> stress test -> results/."""
from __future__ import annotations

import csv
import json
import math
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from . import cop, hyetograph, idf, network, rational, swmm_model

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"

STORM_DURATION_MIN = 120
STORM_DT_MIN = 5

# Stress scenarios.  Uplift values are the two ends of the range quoted for
# extreme daily rainfall in the Third National Climate Change Study (V3),
# joint MSS/MSE news release, 5 Jan 2024 (see docs/sources.md).
STRESS_SCENARIOS = {
    "cc_v3_low": {"T": 10, "uplift": 0.06,
                  "label": "10-yr storm +6% (low end of V3 range)"},
    "cc_v3_high": {"T": 10, "uplift": 0.92,
                   "label": "10-yr storm +92% (high end of V3 range, bounding)"},
    "t100": {"T": 100, "uplift": 0.0,
             "label": "100-yr storm, COP Appendix 4 curve"},
}
SWEEP_UPLIFTS = [round(0.01 * k, 2) for k in range(0, 93)]
SWMM_SWEEP_UPLIFTS = [round(0.04 * k, 2) for k in range(0, 24)] + [0.92]

SOIL_SENSITIVITY = {   # SWMM 5.2 User's Manual Table A.2, sandy loam
    "ga_suction_mm": round(4.33 * 25.4, 1),
    "ga_ksat_mm_hr": round(0.43 * 25.4, 2),
    "ga_initial_deficit": round(0.453 - 0.190, 3),
}

SWMM_FREEBOARD_DEPTH_RATIO = 1.0 - cop.FREEBOARD_FRACTION

# every SWMM run made by main() is logged here (continuity errors reported)
RUN_LOG: list[dict] = []


def r4(x: float) -> float:
    return float(f"{x:.4g}") if isinstance(x, float) else x


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=False)
        f.write("\n")


def run_swmm(net, secs, T, uplift, name, model_dir: Path | None, hydro_override=None):
    """Write the .inp (kept under results/models if model_dir given) and run
    it in a temporary directory so .rpt/.out never land in the repo."""
    inv = rational.inverts(net, secs)
    hy = hyetograph.alternating_block(T, STORM_DURATION_MIN, STORM_DT_MIN, uplift)
    saved = None
    if hydro_override:
        saved = dict(swmm_model.HYDROLOGY)
        swmm_model.HYDROLOGY.update(hydro_override)
    try:
        text = swmm_model.build_inp(net, secs, inv, hy, STORM_DT_MIN,
                                    f"sg-drainage-swmm scenario {name}")
    finally:
        if saved is not None:
            swmm_model.HYDROLOGY.clear()
            swmm_model.HYDROLOGY.update(saved)
    if model_dir is not None:
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / f"{name}.inp").write_text(text)
    tmp = Path(tempfile.mkdtemp(prefix="sgswmm_"))
    try:
        p = tmp / f"{name}.inp"
        p.write_text(text)
        res = swmm_model.run_inp(p)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    RUN_LOG.append({"name": name, "runoff": res.runoff_continuity_pct,
                    "routing": res.routing_continuity_pct})
    return res, inv, hy


def swmm_failures(net, res, secs) -> dict:
    flooded = [n for n, v in res.nodes.items() if v["hours_flooded"] > 0]
    over_fb = [r.id for r in net.reaches
               if res.links[r.id]["max_over_full_depth"] > SWMM_FREEBOARD_DEPTH_RATIO + 1e-9]
    over_v = [r.id for r in net.reaches if res.links[r.id]["max_velocity"] > cop.V_MAX_CONCRETE]
    return {"flooded_nodes": flooded, "reaches_into_freeboard": over_fb,
            "reaches_over_vmax": over_v,
            "flood_volume_m3": round(res.total_flood_volume_m3, 1)}


def failing_reaches(rows: list[rational.ReachResult]) -> dict[str, list[str]]:
    out = {}
    for r in rows:
        crit = []
        if not r.freeboard_ok:
            crit.append("freeboard")
        if not r.vmax_ok:
            crit.append("vmax")
        if not r.froude_ok:
            crit.append("froude")
        if crit:
            out[r.reach] = crit
    return out


def main(write_figures: bool = True) -> dict:
    net = network.load()
    RUN_LOG.clear()
    T_design = cop.design_return_period(net.total_area_ha)
    models = RESULTS / "models"

    # ---------------------------------------------------------- inputs used
    durations, table = idf.load_table()
    inputs = {
        "cop": cop.as_dict(),
        "catchment": {
            "total_area_ha": round(net.total_area_ha, 3),
            "n_subcatchments": len(net.subcatchments),
            "n_reaches": len(net.reaches),
            "n_main_reaches": len(net.main_line()),
            "total_drain_length_m": round(sum(r.length for r in net.reaches), 1),
            "design_return_period_yr": T_design,
            "c_min": round(min(s.c for s in net.subcatchments), 4),
            "c_max": round(max(s.c for s in net.subcatchments), 4),
            "overland_time_values_min": sorted({s.overland_time_min for s in net.subcatchments}),
            "overland_length_min_m": min(s.overland_length_m for s in net.subcatchments),
            "overland_length_max_m": max(s.overland_length_m for s in net.subcatchments),
        },
        "sweep": {"rational_step_pct": round(100 * (SWEEP_UPLIFTS[1] - SWEEP_UPLIFTS[0])),
                  "swmm_step_pct": round(100 * (SWMM_SWEEP_UPLIFTS[1] - SWMM_SWEEP_UPLIFTS[0])),
                  "max_pct": round(100 * SWEEP_UPLIFTS[-1])},
        "catalogue": {"width_min_m": rational.WIDTHS[0], "width_max_m": rational.WIDTHS[-1],
                      "depth_min_m": rational.DEPTHS[0], "depth_max_m": rational.DEPTHS[-1],
                      "step_m": round(rational.WIDTHS[1] - rational.WIDTHS[0], 2)},
        "storm": {"duration_min": STORM_DURATION_MIN, "dt_min": STORM_DT_MIN,
                  "design_peak_block_mm_hr": round(idf.intensity(T_design, STORM_DT_MIN), 1),
                  "design_depth_mm": round(idf.depth_mm(T_design, STORM_DURATION_MIN), 1),
                  "idf_i10_5min": table[10][0], "idf_i10_60min": round(idf.intensity(10, 60), 1),
                  "idf_i100_60min": round(idf.intensity(100, 60), 1)},
        "swmm": {"hydrology": swmm_model.HYDROLOGY, "options": swmm_model.OPTIONS,
                 "impervious_pct": {k: round(100 * v) for k, v in
                                    swmm_model.HYDROLOGY["impervious_fraction"].items()},
                 "soil_sensitivity_sandy_loam": SOIL_SENSITIVITY,
                 "freeboard_depth_ratio": SWMM_FREEBOARD_DEPTH_RATIO},
        "stress": {k: {kk: vv for kk, vv in v.items()} for k, v in STRESS_SCENARIOS.items()},
        "stress_uplift_pct": {k: round(100 * v["uplift"]) for k, v in STRESS_SCENARIOS.items()},
    }
    meta = json.loads((REPO / "data" / "idf_digitisation_meta.json").read_text())
    inputs["idf_digitisation"] = {
        "one_pixel_reading_uncertainty_pct": meta["one_pixel_reading_uncertainty_pct"],
        "max_local_fit_residual_px": meta["max_local_fit_residual_px"],
        "n_durations": len(durations), "duration_min": durations[0], "duration_max": durations[-1],
    }
    write_json(RESULTS / "inputs_used.json", inputs)

    # ------------------------------------------------------------- design
    design = rational.run(net, T_design)
    secs = rational.sections(design)
    write_csv(RESULTS / "design_table.csv", rational.as_rows(design))
    inv = rational.inverts(net, secs)
    write_csv(RESULTS / "design_levels.csv",
              [{"reach": k, **{kk: round(vv, 4) for kk, vv in v.items()}} for k, v in inv.items()])
    out = next(r for r in design if net.nodes[r.to].outfall)
    dsum = {
        "return_period_yr": T_design,
        "n_reaches": len(design),
        "all_compliant": all(r.compliant for r in design),
        "all_converged": all(r.converged for r in design),
        "max_iterations": max(r.iterations for r in design),
        "max_tc_residual_min": max(r.tc_residual_min for r in design),
        "max_utilisation": round(max(r.utilisation for r in design), 3),
        "max_utilisation_reach": max(design, key=lambda r: r.utilisation).reach,
        "min_utilisation": round(min(r.utilisation for r in design), 3),
        "max_velocity_ms": round(max(r.v_ms for r in design), 2),
        "min_velocity_ms": round(min(r.v_ms for r in design), 2),
        "max_froude": round(max(r.froude for r in design), 2),
        "max_y_over_d": round(max(r.y_over_d for r in design), 3),
        "outfall_reach": out.reach,
        "outfall_q_m3s": round(out.q_m3s, 3),
        "outfall_tc_min": round(out.tc_min, 2),
        "outfall_intensity_mm_hr": round(out.intensity_mm_hr, 1),
        "outfall_section": f"{out.width_m:.1f} m x {out.depth_m:.1f} m",
        "n_gradient_changed": sum(not r.gradient_from_ground for r in design),
        "smallest_section": "{:.1f} m x {:.1f} m".format(*min(
            ((r.width_m, r.depth_m) for r in design), key=lambda s: s[0] * s[1])),
        "largest_section": f"{out.width_m:.1f} m x {out.depth_m:.1f} m",
        "max_excavation_depth_m": round(max(net.nodes[r.to].ground - inv[r.reach]["inv_dn"]
                                            for r in design), 2),
    }
    write_json(RESULTS / "design_summary.json", dsum)

    # ------------------------------------------------- design sensitivities
    sens = {}
    for to in (cop.OVERLAND_TIME_MIN, cop.OVERLAND_TIME_MAX):
        alt = rational.run(net, T_design, overland_time_override=to)
        sens[f"overland_{int(to)}min"] = {
            "outfall_q_m3s": round(alt[-1].q_m3s, 3),
            "outfall_q_change_pct": round(100 * (alt[-1].q_m3s / out.q_m3s - 1), 1),
            "n_size_changes": sum((a.width_m, a.depth_m) != (b.width_m, b.depth_m)
                                  for a, b in zip(alt, design)),
        }
    for pct in (-1, 1):
        alt = rational.run(net, T_design, uplift=pct / 100)
        sens[f"idf_{'minus' if pct < 0 else 'plus'}1pct"] = {
            "n_size_changes": sum((a.width_m, a.depth_m) != (b.width_m, b.depth_m)
                                  for a, b in zip(alt, design)),
        }
    write_json(RESULTS / "sensitivity_design.json", sens)

    # ---------------------------------------------------------- SWMM check
    base_res, _, hy_base = run_swmm(net, secs, T_design, 0.0, "design_10yr", models)
    links_rows = []
    for r in design:
        lk = base_res.links[r.reach]
        links_rows.append({
            "reach": r.reach, "rational_q_m3s": round(r.q_m3s, 4),
            "swmm_peak_m3s": lk["max_flow"],
            "swmm_over_rational": round(lk["max_flow"] / r.q_m3s, 3),
            "swmm_max_velocity_ms": lk["max_velocity"],
            "swmm_max_over_full_depth": lk["max_over_full_depth"],
            "rational_y_over_d": round(r.y_over_d, 3),
        })
    write_csv(RESULTS / "swmm_vs_rational.csv", links_rows)
    write_csv(RESULTS / "swmm_design_nodes.csv",
              [{"node": k, **v} for k, v in base_res.nodes.items()])
    # sub-catchment attribution: SWMM peak runoff vs rational Q at its own to
    sub_rows = []
    peak_block = max(hy_base)
    for s in net.subcatchments:
        sp = base_res.subcatchments[s.id]
        q_rat = cop.rational_q(s.c, idf.intensity(T_design, s.overland_time_min), s.area_ha)
        # what fraction of the peak 5-min rainfall rate leaves the sub-catchment
        peak_fraction = sp["peak_runoff"] * cop.RATIONAL_DIVISOR / (peak_block * s.area_ha)
        sub_rows.append({
            "subcatchment": s.id, "land_use": s.land_use, "area_ha": s.area_ha,
            "c_cop": round(s.c, 4), "overland_time_min": s.overland_time_min,
            "i_at_to_mm_hr": round(idf.intensity(T_design, s.overland_time_min), 1),
            "rational_q_m3s": round(q_rat, 4),
            "swmm_peak_m3s": sp["peak_runoff"],
            "swmm_over_rational": round(sp["peak_runoff"] / q_rat, 3),
            "swmm_event_runoff_coeff": sp["runoff_coeff"],
            "swmm_peak_over_peak_rain": round(peak_fraction, 3),
            "duration_factor": round(peak_block / idf.intensity(T_design, s.overland_time_min), 3),
            "runoff_factor": round(peak_fraction / s.c, 3),
        })
    write_csv(RESULTS / "subcatchment_swmm_vs_rational.csv", sub_rows)

    soil_res, _, _ = run_swmm(net, secs, T_design, 0.0, "design_10yr_sandy_loam", None,
                              hydro_override=SOIL_SENSITIVITY)
    base_fail = swmm_failures(net, base_res, secs)
    soil_fail = swmm_failures(net, soil_res, secs)
    ratios = [row["swmm_over_rational"] for row in links_rows]
    swmm_sum = {
        "engine": "EPA SWMM 5.2 via swmm-toolkit",
        "runoff_continuity_error_pct": base_res.runoff_continuity_pct,
        "routing_continuity_error_pct": base_res.routing_continuity_pct,
        "continuity_threshold_pct": 1.0,
        "event_runoff_coefficient": round(base_res.runoff_coefficient, 3),
        "total_precip_mm": base_res.total_precip_mm,
        "peak_block_mm_hr": round(peak_block, 1),
        "swmm_over_rational_min": min(ratios),
        "swmm_over_rational_max": max(ratios),
        "swmm_over_rational_min_pct": round(100 * (min(ratios) - 1)),
        "swmm_over_rational_max_pct": round(100 * (max(ratios) - 1)),
        "outfall_swmm_peak_m3s": base_res.links[out.reach]["max_flow"],
        "outfall_rational_q_m3s": round(out.q_m3s, 3),
        "sub_swmm_over_rational_min": min(r["swmm_over_rational"] for r in sub_rows),
        "sub_swmm_over_rational_max": max(r["swmm_over_rational"] for r in sub_rows),
        "sub_duration_factor_min": min(r["duration_factor"] for r in sub_rows),
        "sub_duration_factor_max": max(r["duration_factor"] for r in sub_rows),
        "sub_runoff_factor_min": min(r["runoff_factor"] for r in sub_rows),
        "sub_runoff_factor_max": max(r["runoff_factor"] for r in sub_rows),
        "sub_event_runoff_coeff_min": min(r["swmm_event_runoff_coeff"] for r in sub_rows),
        "sub_event_runoff_coeff_max": max(r["swmm_event_runoff_coeff"] for r in sub_rows),
        "design": {**base_fail, "n_flooded_nodes": len(base_fail["flooded_nodes"]),
                   "n_reaches_into_freeboard": len(base_fail["reaches_into_freeboard"])},
        "sandy_loam": {**soil_fail, "n_flooded_nodes": len(soil_fail["flooded_nodes"]),
                       "event_runoff_coefficient": round(soil_res.runoff_coefficient, 3),
                       "outfall_swmm_peak_m3s": soil_res.links[out.reach]["max_flow"],
                       "runoff_continuity_error_pct": soil_res.runoff_continuity_pct,
                       "routing_continuity_error_pct": soil_res.routing_continuity_pct},
        "warnings": base_res.warnings,
    }

    # SWMM-led greedy upsizing of the design for the design storm
    swmm_secs, swmm_log = swmm_greedy_upsize(net, secs, T_design, 0.0)
    swmm_sum["greedy_upsizing_design_storm"] = swmm_log
    write_json(RESULTS / "swmm_summary.json", swmm_sum)

    # ------------------------------------------------------------- stress
    stress = {}
    reach_rows = []
    for key, sc in STRESS_SCENARIOS.items():
        chk = rational.run(net, sc["T"], sc["uplift"], mode="check", fixed=secs)
        fails = failing_reaches(chk)
        up = rational.run(net, sc["T"], sc["uplift"], mode="upsize", fixed=secs)
        up_secs = rational.sections(up)
        changed = {r.reach: {"from": f"{secs[r.reach][0]:.1f} x {secs[r.reach][1]:.1f}",
                             "to": f"{r.width_m:.1f} x {r.depth_m:.1f}",
                             "area_increase_pct": round(100 * (r.width_m * r.depth_m /
                                                               (secs[r.reach][0] * secs[r.reach][1]) - 1))}
                   for r in up if (r.width_m, r.depth_m) != secs[r.reach][:2]}
        res_exist, _, _ = run_swmm(net, secs, sc["T"], sc["uplift"], f"{key}_existing", models)
        res_up, _, _ = run_swmm(net, up_secs, sc["T"], sc["uplift"], f"{key}_upsized", models)
        f_exist = swmm_failures(net, res_exist, secs)
        f_up = swmm_failures(net, res_up, up_secs)
        _, greedy_log = swmm_greedy_upsize(net, secs, sc["T"], sc["uplift"], max_rounds=120)
        old_area = sum(secs[r.id][0] * secs[r.id][1] * r.length for r in net.reaches)
        new_area = sum(up_secs[r.id][0] * up_secs[r.id][1] * r.length for r in net.reaches)
        stress[key] = {
            **sc, "uplift_pct": round(100 * sc["uplift"]),
            "rational_failing_reaches": sorted(fails),
            "n_rational_failing": len(fails),
            "rational_fail_criteria": fails,
            "max_utilisation_existing": round(max(r.utilisation for r in chk), 3),
            "outfall_q_m3s": round(chk[-1].q_m3s, 3),
            "upsized_reaches": changed,
            "n_upsized": len(changed),
            "upsized_all_compliant": all(r.compliant for r in up),
            "drain_volume_increase_pct": round(100 * (new_area / old_area - 1), 1),
            "swmm_existing": {**f_exist, "n_flooded_nodes": len(f_exist["flooded_nodes"]),
                              "routing_continuity_error_pct": res_exist.routing_continuity_pct,
                              "runoff_continuity_error_pct": res_exist.runoff_continuity_pct},
            "swmm_upsized": {**f_up, "n_flooded_nodes": len(f_up["flooded_nodes"]),
                             "routing_continuity_error_pct": res_up.routing_continuity_pct,
                             "runoff_continuity_error_pct": res_up.runoff_continuity_pct},
            "swmm_greedy_upsizing": greedy_log,
        }
        for a, b in zip(chk, up):
            reach_rows.append({
                "scenario": key, "reach": a.reach, "q_m3s": round(a.q_m3s, 4),
                "utilisation_existing": round(a.utilisation, 3),
                "fails_existing": ";".join(fails.get(a.reach, [])) or "",
                "existing_section": f"{a.width_m:.1f} x {a.depth_m:.1f}",
                "upsized_section": f"{b.width_m:.1f} x {b.depth_m:.1f}",
                "upsized_utilisation": round(b.utilisation, 3),
                "swmm_existing_max_over_full_depth": res_exist.links[a.reach]["max_over_full_depth"],
                "swmm_upsized_max_over_full_depth": res_up.links[a.reach]["max_over_full_depth"],
            })
    write_csv(RESULTS / "stress_reaches.csv", reach_rows)

    # uplift sweep - rational (existing sections)
    sweep_rows = []
    first_fail = {r.id: None for r in net.reaches}
    for u in SWEEP_UPLIFTS:
        chk = rational.run(net, T_design, u, mode="check", fixed=secs)
        fails = failing_reaches(chk)
        for rid in fails:
            if first_fail[rid] is None:
                first_fail[rid] = u
        sweep_rows.append({"uplift_pct": round(100 * u), "n_failing": len(fails),
                           "max_utilisation": round(max(r.utilisation for r in chk), 4),
                           **{f"util_{r.reach}": round(r.utilisation, 4) for r in chk}})
    write_csv(RESULTS / "uplift_sweep_rational.csv", sweep_rows)
    swmm_sweep = []
    for u in SWMM_SWEEP_UPLIFTS:
        res, _, _ = run_swmm(net, secs, T_design, u, "sweep", None)
        f = swmm_failures(net, res, secs)
        swmm_sweep.append({"uplift_pct": round(100 * u), "flood_volume_m3": f["flood_volume_m3"],
                           "n_flooded_nodes": len(f["flooded_nodes"]),
                           "n_reaches_into_freeboard": len(f["reaches_into_freeboard"]),
                           "routing_continuity_error_pct": res.routing_continuity_pct,
                           "runoff_continuity_error_pct": res.runoff_continuity_pct})
    write_csv(RESULTS / "uplift_sweep_swmm.csv", swmm_sweep)
    ff = {k: (None if v is None else round(100 * v)) for k, v in first_fail.items()}
    first = [v for v in ff.values() if v is not None]
    stress_sum = {
        "scenarios": stress,
        "first_failure_uplift_pct": ff,
        "min_first_failure_uplift_pct": min(first) if first else None,
        "max_first_failure_uplift_pct": max(first) if first else None,
        "n_reaches_never_fail_in_sweep": sum(v is None for v in ff.values()),
        "n_failing_at_v3_high": stress["cc_v3_high"]["n_rational_failing"],
    }
    write_json(RESULTS / "stress_summary.json", stress_sum)

    # tide and sea-level rise at the outfall (its SWMM runs join RUN_LOG)
    from . import tide_pipeline
    tide_sum = tide_pipeline.main(net, design, secs, write_figures=write_figures)

    write_json(RESULTS / "swmm_run_log.json", {
        "n_runs": len(RUN_LOG),
        "max_abs_runoff_continuity_error_pct": max(abs(r["runoff"]) for r in RUN_LOG),
        "max_abs_routing_continuity_error_pct": max(abs(r["routing"]) for r in RUN_LOG),
        "max_abs_continuity_error_pct": max(max(abs(r["runoff"]), abs(r["routing"]))
                                            for r in RUN_LOG),
        "threshold_pct": 1.0,
        "runs": RUN_LOG,
    })

    # hyetographs for the record
    hys = {"design_10yr": hy_base}
    for key, sc in STRESS_SCENARIOS.items():
        hys[key] = hyetograph.alternating_block(sc["T"], STORM_DURATION_MIN, STORM_DT_MIN,
                                                sc["uplift"])
    write_csv(RESULTS / "hyetographs.csv",
              [{"start_min": k * STORM_DT_MIN, **{n: round(v[k], 3) for n, v in hys.items()}}
               for k in range(len(hy_base))])

    if write_figures:
        from . import plots
        plots.make_all(net, design, secs, inv, base_res, stress, RESULTS / "figures")
    return {"design": dsum, "swmm": swmm_sum, "stress": stress_sum, "tide": tide_sum}


def swmm_greedy_upsize(net, secs, T, uplift, max_rounds: int = 40):
    """Heuristic: repeatedly enlarge the most-downstream reaches that SWMM shows
    flowing into the freeboard (max depth > 0.85 D) or overtopping at their
    upstream node, by one catalogue step (next larger area with W, D not
    reduced, gradient unchanged), until SWMM shows neither.  Not proven
    minimal - reported as an indication of what the dynamic check asks for."""
    cur = dict(secs)
    log = {"rounds": 0, "changed": {}}
    for rnd in range(1, max_rounds + 1):
        res, _, _ = run_swmm(net, cur, T, uplift, "greedy", None)
        bad = set()
        for r in net.reaches:
            lk = res.links[r.id]
            if lk["max_over_full_depth"] > SWMM_FREEBOARD_DEPTH_RATIO + 1e-9:
                bad.add(r.id)
            if res.nodes[r.frm]["hours_flooded"] > 0:
                bad.add(r.id)
        if not bad:
            log["rounds"] = rnd - 1
            break
        # fix the most downstream failing reaches first (backwater acts upstream)
        def downstream_bad(rid):
            r = net.reach(rid)
            nxt = net.outgoing(r.to)
            while nxt:
                if nxt[0].id in bad:
                    return True
                nxt = net.outgoing(nxt[0].to)
            return False
        targets = [rid for rid in bad if not downstream_bad(rid)]
        for rid in targets:
            b, d, s = cur[rid]
            area = b * d
            for bb, dd in rational.CATALOGUE:
                if bb >= b - 1e-9 and dd >= d - 1e-9 and bb * dd > area + 1e-9:
                    cur[rid] = (bb, dd, s)
                    break
    else:
        log["rounds"] = max_rounds
        log["not_converged"] = True
    for rid in cur:
        if cur[rid][:2] != secs[rid][:2]:
            log["changed"][rid] = {"from": f"{secs[rid][0]:.1f} x {secs[rid][1]:.1f}",
                                   "to": f"{cur[rid][0]:.1f} x {cur[rid][1]:.1f}"}
    log["n_changed"] = len(log["changed"])
    old = sum(secs[r.id][0] * secs[r.id][1] * r.length for r in net.reaches)
    new = sum(cur[r.id][0] * cur[r.id][1] * r.length for r in net.reaches)
    log["drain_volume_increase_pct"] = round(100 * (new / old - 1), 1)
    res, _, _ = run_swmm(net, cur, T, uplift, "greedy_final", None)
    log["final_flood_volume_m3"] = round(res.total_flood_volume_m3, 1)
    log["final_max_over_full_depth"] = max(v["max_over_full_depth"] for v in res.links.values())
    log["final_routing_continuity_error_pct"] = res.routing_continuity_pct
    log["final_runoff_continuity_error_pct"] = res.runoff_continuity_pct
    log["final_max_velocity_ms"] = max(v["max_velocity"] for v in res.links.values())
    return cur, log
