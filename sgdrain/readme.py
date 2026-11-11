"""Render README.md from docs/README.template.md and the files in results/.

Placeholders:
  {{ file.key.subkey }}            value from results/<file>.json
  {{ file.key | .2f }}             with a format spec
  {{ file.key | list }}            list joined with ", "
  {{ file.key | pct }}             fraction -> percent with no decimals
  {{ table:<name> }}               a markdown table built from a results CSV

Every number in README.md therefore comes from a results file written by
scripts/run_all.py; tests/test_readme.py re-renders and compares.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "docs" / "README.template.md"
README = REPO / "README.md"
RESULTS = REPO / "results"

PLACEHOLDER = re.compile(r"\{\{\s*([^}|]+?)\s*(?:\|\s*([^}]+?)\s*)?\}\}")


def _load(name: str):
    return json.loads((RESULTS / f"{name}.json").read_text())


def _csv(name: str) -> list[dict]:
    with open(RESULTS / f"{name}.csv", newline="") as f:
        return list(csv.DictReader(f))


NOT_RUN = "(mutation test not run yet)"


def lookup(key: str):
    parts = key.split(".")
    if parts[0] == "mutation_report" and not (RESULTS / "mutation_report.json").exists():
        return NOT_RUN
    obj = _load(parts[0])
    try:
        for p in parts[1:]:
            obj = obj[int(p)] if isinstance(obj, list) else obj[p]
    except (KeyError, IndexError):
        # a report written before a group of mutants existed lacks their keys
        if parts[0] == "mutation_report":
            return NOT_RUN
        raise
    return obj


def fmt(value, spec: str | None) -> str:
    if isinstance(value, str) and spec in ("list", "keys", "len"):
        return value
    if spec is None:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    if spec == "yesno":
        return "yes" if value else "no"
    if spec == "list":
        return ", ".join(str(v) for v in value) if value else "none"
    if spec == "pct":
        return f"{100 * value:.0f}"
    if spec == "len":
        return str(len(value))
    if spec == "keys":
        return ", ".join(value.keys()) if value else "none"
    if spec == "slope":
        return f"1:{1 / value:.0f}"
    if spec == "abs":
        return fmt(abs(value), None)
    return format(value, spec)


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def table_design() -> str:
    rows = []
    for r in _csv("design_table"):
        rows.append([r["reach"], f"{r['frm']}->{r['to']}", f"{float(r['length_m']):.0f}",
                     f"1:{1 / float(r['slope']):.0f}", f"{float(r['area_ha']):.2f}",
                     f"{float(r['c_eq']):.3f}", f"{float(r['tc_min']):.1f}",
                     f"{float(r['intensity_mm_hr']):.1f}", f"{float(r['q_m3s']):.3f}",
                     f"{float(r['width_m']):.1f} x {float(r['depth_m']):.1f}",
                     f"{float(r['y_over_d']):.2f}", f"{float(r['v_ms']):.2f}",
                     f"{float(r['froude']):.2f}", f"{float(r['utilisation']):.2f}",
                     "yes" if r["compliant"] == "True" else "NO"])
    return _md_table(["Reach", "Nodes", "L (m)", "Slope", "A (ha)", "C", "tc (min)",
                      "I (mm/hr)", "Qr (m3/s)", "W x D (m)", "y/D", "V (m/s)", "Fr",
                      "Util.", "COP checks"], rows)


def table_swmm() -> str:
    rows = []
    for r in _csv("swmm_vs_rational"):
        rows.append([r["reach"], f"{float(r['rational_q_m3s']):.3f}",
                     f"{float(r['swmm_peak_m3s']):.3f}", f"{float(r['swmm_over_rational']):.2f}",
                     f"{float(r['rational_y_over_d']):.2f}",
                     f"{float(r['swmm_max_over_full_depth']):.2f}",
                     f"{float(r['swmm_max_velocity_ms']):.2f}"])
    return _md_table(["Reach", "Rational Qr (m3/s)", "SWMM peak (m3/s)", "SWMM / rational",
                      "Rational y/D", "SWMM max y/D", "SWMM max V (m/s)"], rows)


def table_subcatchments() -> str:
    rows = []
    for r in _csv("subcatchment_swmm_vs_rational"):
        rows.append([r["subcatchment"], r["land_use"], f"{float(r['c_cop']):.2f}",
                     f"{float(r['overland_time_min']):.0f}",
                     f"{float(r['rational_q_m3s']):.3f}", f"{float(r['swmm_peak_m3s']):.3f}",
                     f"{float(r['swmm_over_rational']):.2f}", f"{float(r['duration_factor']):.2f}",
                     f"{float(r['runoff_factor']):.2f}"])
    return _md_table(["Sub-catchment", "Land use", "COP C", "to (min)", "Rational Q (m3/s)",
                      "SWMM peak (m3/s)", "Ratio", "Duration factor", "Runoff factor"], rows)


def table_stress() -> str:
    s = _load("stress_summary")["scenarios"]
    rows = []
    for key, v in s.items():
        g = v["swmm_greedy_upsizing"]
        rows.append([
            v["label"],
            f"{v['max_utilisation_existing']:.2f}",
            f"{v['n_rational_failing']} / {len(_csv('design_table'))}",
            f"{v['swmm_existing']['n_flooded_nodes']} nodes, {v['swmm_existing']['flood_volume_m3']:.0f} m3",
            f"{v['n_upsized']} reaches, +{v['drain_volume_increase_pct']:.1f}%",
            f"{v['swmm_upsized']['flood_volume_m3']:.0f} m3",
            f"{g['n_changed']} reaches, +{g['drain_volume_increase_pct']:.1f}%",
        ])
    return _md_table(["Scenario", "Max utilisation (design sizes)", "Reaches failing (rational)",
                      "SWMM overtopping (design sizes)", "Minimum rational upsizing",
                      "SWMM overtopping after rational upsizing",
                      "SWMM-led greedy upsizing"], rows)


def table_upsizing() -> str:
    s = _load("stress_summary")["scenarios"]
    design = {r["reach"]: f"{float(r['width_m']):.1f} x {float(r['depth_m']):.1f}"
              for r in _csv("design_table")}
    keys = list(s.keys())
    rows = []
    for rid, sec in design.items():
        row = [rid, sec]
        for k in keys:
            ch = s[k]["upsized_reaches"].get(rid)
            row.append(ch["to"] if ch else "-")
        rows.append(row)
    return _md_table(["Reach", "Design W x D (m)"] +
                     [f"Rational upsizing: {s[k]['label']}" for k in keys], rows)


def table_first_failure() -> str:
    ff = _load("stress_summary")["first_failure_uplift_pct"]
    rows = [[k, "-" if v is None else f"+{v}%"] for k, v in ff.items()]
    return _md_table(["Reach", "Smallest uplift that breaks a COP criterion"], rows)


def _slr_labels() -> dict:
    return {s["id"]: s["label"] for s in _load("tide_inputs")["coastal"]["slr_scenarios"]}


def _num(v) -> float:
    return float(v) if v not in ("", None) else float("nan")


def _list(v: str) -> str:
    return ", ".join(v.split(";")) if v else "none"


def table_tide_base() -> str:
    labels = _slr_labels()
    rows = []
    for r in _csv("tide_scenarios"):
        if r["storm"] != "design_10yr" or r["gated"] != "False":
            continue
        gated = next(g for g in _csv("tide_scenarios") if g["storm"] == r["storm"]
                     and g["sizes"] == r["sizes"] and g["slr_id"] == r["slr_id"] and g["gated"] == "True")
        rel = _num(r["peak_above_outfall_invert_m"])
        rows.append([labels[r["slr_id"]], f"{_num(r['peak_sea_level_shd']):.2f}",
                     f"{abs(rel):.2f} {'above' if rel > 0 else 'below'}",
                     _list(r["gvf_fail_due_to_tide"]), f"{_num(r['gvf_extent_main_m']):.0f}",
                     f"{_num(r['d_flood_m3']):+.0f} / {_num(gated['d_flood_m3']):+.0f}",
                     f"{_num(r['max_head_rise_m']):.3f}"])
    return _md_table(["Sea level at the outfall", "High water (m SHD)", "vs outfall invert (m)",
                      "Reaches losing the COP freeboard (steady)", "Backwater up the main drain (m)",
                      "SWMM extra overtopping, open / flap-gated (m3)", "Largest rise of a node's max level (m)"],
                     rows)


def table_tide_storms() -> str:
    labels = _slr_labels()
    s = _load("tide_summary")
    crit = {(c["storm"], c["sizes"]): c for c in s["critical_tailwater"]}
    stress = _load("stress_summary")["scenarios"]
    names = {"design_10yr": f"{_load('design_summary')['return_period_yr']}-yr design storm",
             **{k: v["label"] for k, v in stress.items()}}
    ids = [x["id"] for x in _load("tide_inputs")["coastal"]["slr_scenarios"]]
    rows, seen = [], []
    allrows = _csv("tide_scenarios")
    for r in allrows:
        key = (r["storm"], r["sizes"])
        if key in seen:
            continue
        seen.append(key)
        c = crit[key]
        cells = []
        for sid in ids:
            m = next(x for x in allrows if (x["storm"], x["sizes"]) == key and x["slr_id"] == sid
                     and x["gated"] == "False")
            cells.append("sea above ground" if m["status"] != "run" else f"{_num(m['d_flood_m3']):+.0f}")
        rows.append([names[r["storm"]], r["sizes"], c["outfall_section"], f"{c['outfall_invert_shd']:.2f}",
                     "fails without tide" if c["tw_crit_shd"] is None else f"{c['tw_crit_shd']:.2f}"] + cells)
    return _md_table(["Storm", "Drain sizes", "Outfall drain W x D (m)", "Outfall invert (m SHD)",
                      "Highest outfall level keeping the COP freeboard (m SHD)"] +
                     [f"SWMM extra overtopping (m3): {labels[i]}" for i in ids], rows)


def table_tide_datum() -> str:
    labels = _slr_labels()
    ids = [x["id"] for x in _load("tide_inputs")["coastal"]["slr_scenarios"]]
    rows_in = _csv("tide_datum_sensitivity")
    grounds = []
    for r in rows_in:
        if r["outfall_ground_shd"] not in grounds:
            grounds.append(r["outfall_ground_shd"])
    rows = []
    for g in grounds:
        cells = []
        for sid in ids:
            r = next(x for x in rows_in if x["outfall_ground_shd"] == g and x["slr_id"] == sid)
            if r["status"] != "run":
                cells.append(f"sea {-_num(r['peak_below_outfall_ground_m']):.2f} m above ground")
                continue
            rel = _num(r["peak_above_outfall_invert_m"])
            effect = (r["gvf_fail_due_to_tide"] or _num(r["d_flood_m3_open"]) != 0
                      or _num(r["max_head_rise_m_open"]) >= _load("tide_inputs")["settings"]["swmm_rise_tol_m"])
            where = f"high water {abs(rel):.2f} m {'above' if rel > 0 else 'below'} the outfall invert"
            if not effect:
                cells.append(f"no effect ({where})")
            else:
                cells.append(f"{_num(r['d_flood_m3_open']):+.0f} m3; freeboard lost: "
                             f"{_list(r['gvf_fail_due_to_tide'])} ({where})")
        rows.append([f"{_num(g):.1f}"] + cells)
    return _md_table(["Outfall ground (m SHD)"] + [labels[i] for i in ids], rows)


def table_tide_min_ground() -> str:
    labels = _slr_labels()
    rows = []
    for m in _load("tide_summary")["min_outfall_ground"]:
        rows.append([labels[m["slr_id"]], f"{m['hw_shd']:.2f}",
                     f"{m['min_outfall_ground_shd_cop_freeboard']:.2f}",
                     f"{m['min_outfall_ground_shd_swmm_no_rise']:.2f}",
                     f"{m['margin_at_cop_platform_level_m']:+.2f}"])
    s = _load("tide_summary")
    tol = _load("tide_inputs")["settings"]["swmm_rise_tol_m"]
    return _md_table(["Sea level", "High water (m SHD)",
                      "Lowest outfall ground keeping the COP freeboard (m SHD)",
                      f"Lowest outfall ground with no SWMM rise of {100 * tol:.0f} cm or more "
                      f"(m SHD, sweep steps of {s['sweep_step_near_ground_m']} m)",
                      "Margin if the outfall ground is at the COP minimum platform level (m)"], rows)


def table_tide_sweep() -> str:
    rows = []
    for r in _csv("tide_level_sweep"):
        if (_num(r["d_flood_m3_open"]) == 0 and _num(r["d_flood_m3_gated"]) == 0
                and _num(r["gvf_max_rise_m"]) == 0 and _num(r["max_head_rise_m_open"]) == 0):
            continue
        up = r.get("upsize_status") or "-"
        if up == "infeasible":
            up = f"infeasible ({_list(r['upsize_infeasible'])})"
        rows.append([f"{_num(r['hw_minus_outfall_ground_m']):+.2f}", f"{_num(r['hw_shd_at_base_datum']):.2f}",
                     _list(r["gvf_fail_due_to_tide"]), f"{_num(r['gvf_extent_main_m']):.0f}",
                     f"{_num(r['d_flood_m3_open']):+.0f} / {_num(r['d_flood_m3_gated']):+.0f}",
                     f"{_num(r['max_head_rise_m_open']):.3f}", f"{_num(r['swmm_extent_m_open']):.0f}", up])
    tol = _load("tide_inputs")["settings"]["swmm_rise_tol_m"]
    return _md_table(["High water minus outfall ground (m)", "High water at the base assumption (m SHD)",
                      "Reaches losing the COP freeboard (steady)", "Backwater up the main drain, steady (m)",
                      "SWMM extra overtopping, open / flap-gated (m3)", "Largest rise of a node's max level (m)",
                      f"SWMM: furthest main-drain node raised {100 * tol:.0f} cm or more (m from outfall)",
                      "Drain upsizing that restores the freeboard"], rows)


def table_tide_pump() -> str:
    s = _load("tide_summary")
    stress = _load("stress_summary")["scenarios"]
    names = {"design_10yr": f"{_load('design_summary')['return_period_yr']}-yr design storm",
             **{k: v["label"] for k, v in stress.items()}}
    fr = _load("tide_inputs")["settings"]["pump_fractions"]
    rows = []
    for tag, v in s["pump"]["storms"].items():
        storm, sizes = tag.rsplit("_", 1)
        to = {t["pump_fraction_of_peak"]: t for t in v["trade_off"]}
        rows.append([names[storm], "design" if sizes == "design" else "rational upsizing",
                     f"{v['peak_inflow_m3s']:.2f}", f"{v['event_volume_m3']:.0f}"] +
                    [f"{to[f]['storage_m3']:.0f}" for f in fr if f < 1.0])
    return _md_table(["Storm", "Drain sizes", "Peak inflow = pump with no sump (m3/s)",
                      "Inflow volume (m3)"] +
                     [f"Sump for a pump at {100 * f:.0f}% of peak (m3)" for f in fr if f < 1.0], rows)


TABLES = {
    "design": table_design,
    "swmm": table_swmm,
    "subcatchments": table_subcatchments,
    "stress": table_stress,
    "upsizing": table_upsizing,
    "first_failure": table_first_failure,
    "tide_base": table_tide_base,
    "tide_storms": table_tide_storms,
    "tide_datum": table_tide_datum,
    "tide_min_ground": table_tide_min_ground,
    "tide_sweep": table_tide_sweep,
    "tide_pump": table_tide_pump,
}


def render(template: str | None = None) -> str:
    text = TEMPLATE.read_text(encoding="utf-8") if template is None else template

    def sub(m: re.Match) -> str:
        key, spec = m.group(1).strip(), m.group(2)
        if key.startswith("table:"):
            return TABLES[key.split(":", 1)[1]]()
        return fmt(lookup(key), spec.strip() if spec else None)

    return PLACEHOLDER.sub(sub, text)


def write() -> None:
    README.write_text(render(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    write()
