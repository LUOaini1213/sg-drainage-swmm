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


def lookup(key: str):
    parts = key.split(".")
    if parts[0] == "mutation_report" and not (RESULTS / "mutation_report.json").exists():
        return "(mutation test not run yet)"
    obj = _load(parts[0])
    for p in parts[1:]:
        obj = obj[int(p)] if isinstance(obj, list) else obj[p]
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


TABLES = {
    "design": table_design,
    "swmm": table_swmm,
    "subcatchments": table_subcatchments,
    "stress": table_stress,
    "upsizing": table_upsizing,
    "first_failure": table_first_failure,
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
