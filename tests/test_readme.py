"""README numbers must come from results/ files - never typed by hand."""
import re
from pathlib import Path

import pytest

from sgdrain import readme
from conftest import read_csv, read_json

REPO = Path(__file__).resolve().parents[1]

# Literal digits allowed in the template: clause / table / page / version
# references and dates, never results.
ALLOWED = [
    r"Cl(?:ause|\.)s? \d+(?:\.\d+)*(?:,? (?:and |to )?\d+(?:\.\d+)*)*",
    r"\bAppendix \d+", r"Addendum No\. \d+", r"Drawing No\. \d+", r"S/No\. \d+",
    r"Tables? A\.\d+(?:,? (?:and )?A\.\d+)*", r"\bch\. \d+", r"Python 3\.\d+", r"SWMM 5\.\d+",
    r"EPA/600/R-22/030", r"\b(?:19|20|21)\d\d\b", r"\b\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December)\b",
    r"\bV3\b", r"\bm3\b", r"SHA-256", r"Version 5\.2", r"(?m)^\d+\. ",
    r"\bSSP\d-\d\.\d\b", r"\bTable \d+\.\d+\b", r"\bChapter \d+\b", r"\bm2\b",
    r"\bA[12]\b",                      # labels of the two datum assumptions
]


def _strip(text: str) -> str:
    text = re.sub(r"\{\{[^}]*\}\}", " ", text)                 # placeholders
    text = re.sub(r"```.*?```", " ", text, flags=re.S)         # code blocks
    text = re.sub(r"`[^`]*`", " ", text)                       # inline code
    text = re.sub(r"\]\([^)]*\)", "]", text)                   # link targets
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    for pat in ALLOWED:
        text = re.sub(pat, " ", text)
    return text


def test_readme_is_rendered_from_results():
    assert (REPO / "README.md").read_text(encoding="utf-8") == readme.render(), \
        "README.md is stale: run python scripts/run_all.py --readme"


def test_template_has_no_hand_typed_numbers():
    left = _strip(readme.TEMPLATE.read_text(encoding="utf-8"))
    digits = re.findall(r"[^\s]*\d[^\s]*", left)
    assert digits == [], f"hand-typed numbers in template: {digits}"


def test_all_placeholders_resolve():
    for m in readme.PLACEHOLDER.finditer(readme.TEMPLATE.read_text(encoding="utf-8")):
        key = m.group(1).strip()
        if not key.startswith("table:"):
            readme.lookup(key)


def test_spot_check_numbers_against_raw_csv():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    rows = read_csv("design_table.csv")
    umax = max(float(r["utilisation"]) for r in rows)
    assert f"| {umax:.3f} (reach " in text
    swmm = read_csv("swmm_vs_rational.csv")
    ratios = [float(r["swmm_peak_m3s"]) / float(r["rational_q_m3s"]) for r in swmm]
    assert f"| {min(ratios):.2f} to {max(ratios):.2f} across the reaches" in text
    s = read_json("swmm_summary.json")
    assert f"runoff {s['runoff_continuity_error_pct']}%, routing {s['routing_continuity_error_pct']}%" in text
    st = read_json("stress_summary.json")
    assert f"at +{st['min_first_failure_uplift_pct']}% intensity" in text
    # every reach of the design table appears in the README design table
    for r in rows:
        assert f"| {r['reach']} | {r['frm']}->{r['to']} |" in text


def test_spot_check_tide_numbers_against_raw_results():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    s = read_json("tide_summary.json")
    inp = read_json("tide_inputs.json")
    assert f"keeps the COP freeboard | {s['design_tw_crit_shd']:.2f} m SHD" in text
    assert f"outfall ground at {inp['datum']['outfall_ground_shd']:.1f} m SHD (assumption)" in text
    for sc in inp["coastal"]["slr_scenarios"]:
        assert f"| {sc['label']} |" in text
    rows = [r for r in read_csv("tide_scenarios.csv") if r["storm"] == "design_10yr" and r["gated"] == "False"]
    for r in rows:
        assert f"| {float(r['peak_sea_level_shd']):.2f} |" in text
    sens = read_csv("tide_datum_sensitivity.csv")
    n_sea = sum(r["status"] != "run" for r in sens)
    assert text.count("m above ground |") + text.count("m above ground\n") >= 1
    assert sum(text.count(f"sea {-float(r['peak_below_outfall_ground_m']):.2f} m above ground")
               for r in sens if r["status"] != "run") >= n_sea
    for m in s["min_outfall_ground"]:
        assert f"| {m['min_outfall_ground_shd_cop_freeboard']:.2f} |" in text
    v = s["pump"]["storms"]["design_10yr_design"]
    assert f"| {v['peak_inflow_m3s']:.2f} | {v['event_volume_m3']:.0f} |" in text
    # the assumption is labelled as such, next to the official anchor it uses
    assert "ASSUMPTIONS, needed because the catchment is synthetic" in text
    assert "Cl. 2.1.1(a)(i)" in text


def test_disclaimer_near_top():
    head = (REPO / "README.md").read_text(encoding="utf-8")[:1200]
    for phrase in ("SYNTHETIC", "not a PUB-approved design", "professional engineering advice",
                   "personal learning project"):
        assert phrase.lower() in head.lower(), phrase


def test_no_local_paths_or_secrets_committed():
    bad = re.compile(r"[A-Za-z]:\\Users|[A-Za-z]:/Users|/home/\w+|AppData|api[_-]?key|password",
                     re.I)
    for p in REPO.rglob("*"):
        if any(part in {".venv", ".git", "__pycache__", ".pytest_cache", "_work"} for part in p.parts):
            continue
        if p.is_file() and p.suffix in {".py", ".md", ".json", ".csv", ".inp", ".yml", ".txt", ".ini"}:
            if p.name == "test_readme.py":
                continue
            assert not bad.search(p.read_text(encoding="utf-8", errors="replace")), p
