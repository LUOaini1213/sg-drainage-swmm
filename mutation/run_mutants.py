"""Mutation test of the test suite.

Each mutant is one deliberate bug (a single exact-string replacement in the
source).  For every mutant the repository is copied to a scratch directory,
the bug is applied, the file is byte-compiled, and the full pytest suite is
run.  A mutant is *killed* if the suite fails.  The unmodified suite is run
first and must pass, otherwise the script stops.

    python mutation/run_mutants.py [--workers 4]

Writes results/mutation_report.json and re-renders README.md.
"""
from __future__ import annotations

import argparse
import json
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# (id, file, original snippet, mutated snippet, what the bug means)
MUTANTS = [
    ("M01", "sgdrain/hydraulics.py", "hydraulic_radius(b, y) ** (2.0 / 3.0)",
     "hydraulic_radius(b, y) ** (1.0 / 2.0)", "Manning: R exponent 1/2 instead of 2/3"),
    ("M02", "sgdrain/hydraulics.py", "* math.sqrt(s)", "* s",
     "Manning: slope not square-rooted"),
    ("M03", "sgdrain/cop.py", "RATIONAL_DIVISOR = 360.0", "RATIONAL_DIVISOR = 36.0",
     "Rational formula divisor 36 instead of 360"),
    ("M04", "sgdrain/cop.py", "FREEBOARD_FRACTION = 0.15", "FREEBOARD_FRACTION = 0.10",
     "freeboard 10% instead of 15%"),
    ("M05", "sgdrain/cop.py", "FROUDE_MAX = 0.8", "FROUDE_MAX = 1.0",
     "Froude limit 1.0 instead of 0.8"),
    ("M06", "sgdrain/cop.py", "if total_area_ha <= RETURN_PERIOD_BY_AREA[1][0]:",
     "if total_area_ha < RETURN_PERIOD_BY_AREA[1][0]:",
     "return-period rule: 1000 ha falls into the 50-yr class"),
    ("M07", "sgdrain/cop.py", "return sum(RUNOFF_C[k] * f for k, f in fractions.items())",
     "return sum(RUNOFF_C[k] for k in fractions) / len(fractions)",
     "runoff coefficient not area-weighted"),
    ("M08", "sgdrain/rational.py", "tc_new = tc_up + r.length / (60.0 * max(chk.v, 1e-6))",
     "tc_new = tc_up + r.length / (max(chk.v, 1e-6))",
     "drain flow time in seconds added to minutes"),
    ("M09", "sgdrain/rational.py",
     "tc_up = max(to_times + [out[u.id].tc_min for u in net.incoming(r.frm)])",
     "tc_up = min(to_times + [out[u.id].tc_min for u in net.incoming(r.frm)])",
     "tc at a junction takes the shortest, not longest, upstream time"),
    ("M10", "sgdrain/rational.py", "subs = net.contributing_subs(r.frm)",
     "subs = net.subs_at(r.frm)", "upstream area not accumulated"),
    ("M11", "sgdrain/rational.py", "        if abs(tc_new - tc) < TC_TOL_MIN:",
     "        if True:", "tc iteration stops after the first guess"),
    ("M12", "sgdrain/rational.py", "key=lambda s: (s[0] * s[1], s[1], s[0]))",
     "key=lambda s: (-s[0] * s[1], s[1], s[0]))", "catalogue searched largest-first"),
    ("M13", "sgdrain/rational.py", "vmin_ok=v >= cop.V_MIN - 1e-12,", "vmin_ok=True,",
     "minimum self-cleansing velocity not checked"),
    ("M14", "sgdrain/rational.py", "chk = select_section(q, s0, min_b=b0, min_d=d0)",
     "chk = select_section(q, s0)", "upsizing allowed to shrink sections"),
    ("M15", "sgdrain/rational.py", "            inv_up = min(inv_up, out[u.id][\"inv_dn\"])",
     "            pass", "drain may start above the inverts flowing into it"),
    ("M16", "sgdrain/idf.py",
     "li = (1 - w) * math.log(vals[j]) + w * math.log(vals[j + 1])",
     "li = math.log((1 - w) * vals[j] + w * vals[j + 1])",
     "IDF interpolated linearly instead of log-log"),
    ("M17", "sgdrain/idf.py", "return math.exp(li) * (1.0 + uplift)",
     "return math.exp(li) + uplift", "climate uplift added instead of multiplied"),
    ("M18", "sgdrain/hyetograph.py", "centre = (n - 1) // 2", "centre = 0",
     "hyetograph peak at the start instead of the centre"),
    ("M19", "sgdrain/hyetograph.py", "return [d * 60.0 / dt_min for d in blocks]",
     "return [d / dt_min for d in blocks]", "hyetograph depth->intensity unit error"),
    ("M20", "sgdrain/swmm_model.py", "{cop.MANNING_N['concrete']}", "0.013",
     "SWMM conduits use n = 0.013 instead of the COP 0.015"),
]

IGNORE = shutil.ignore_patterns(".venv", ".git", "__pycache__", ".pytest_cache", "_work",
                                "*.rpt", "*.out", "*.pdf")


def copy_repo(dst: Path) -> Path:
    target = dst / "repo"
    shutil.copytree(REPO, target, ignore=IGNORE)
    return target


def run_pytest(cwd: Path, timeout: int = 900) -> tuple[int, str, float]:
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-o", "addopts=",
                            "-p", "no:cacheprovider"],
                           cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -999, f"TIMEOUT after {timeout}s\n{e.stdout or ''}", time.time() - t0


def run_mutant(m) -> dict:
    mid, rel, old, new, desc = m
    with tempfile.TemporaryDirectory(prefix=f"mut_{mid}_") as tmp:
        repo = copy_repo(Path(tmp))
        f = repo / rel
        src = f.read_text(encoding="utf-8")
        n = src.count(old)
        if n != 1:
            return {"id": mid, "file": rel, "description": desc, "status": "invalid",
                    "detail": f"original snippet found {n} times"}
        f.write_text(src.replace(old, new), encoding="utf-8")
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:
            return {"id": mid, "file": rel, "description": desc, "status": "compile_error",
                    "detail": str(e)}
        code, out, secs = run_pytest(repo)
    failed = re.findall(r"^(?:FAILED|ERROR) (\S+)", out, flags=re.M)
    return {"id": mid, "file": rel, "description": desc, "original": old, "mutated": new,
            "compiles": True, "status": "killed" if code != 0 else "survived",
            "pytest_exit_code": code, "first_failing_test": failed[0] if failed else None,
            "seconds": round(secs, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="mut_base_") as tmp:
        repo = copy_repo(Path(tmp))
        code, out, secs = run_pytest(repo)
    m = re.search(r"(\d+) passed", out)
    if code != 0 or not m:
        print(out[-3000:])
        raise SystemExit("baseline suite does not pass - fix that before mutation testing")
    baseline = int(m.group(1))
    print(f"baseline: {baseline} passed in {secs:.0f}s")

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_mutant, MUTANTS))
    for r in results:
        print(f"{r['id']} {r['status']:<9} {r['description']}  [{r.get('first_failing_test')}]")

    valid = [r for r in results if r["status"] in ("killed", "survived")]
    report = {
        "baseline_passed": baseline,
        "baseline_seconds": round(secs, 1),
        "n_mutants": len(MUTANTS),
        "n_valid": len(valid),
        "all_compile": all(r.get("compiles") for r in results),
        "n_killed": sum(r["status"] == "killed" for r in results),
        "n_survived": sum(r["status"] == "survived" for r in results),
        "survivors": [f"{r['id']} ({r['description']})" for r in results
                      if r["status"] == "survived"],
        "invalid": [r["id"] for r in results if r["status"] not in ("killed", "survived")],
        "mutants": results,
    }
    out_path = REPO / "results" / "mutation_report.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    sys.path.insert(0, str(REPO))
    from sgdrain import readme
    readme.write()
    print(f"killed {report['n_killed']}/{report['n_mutants']}; report -> results/mutation_report.json")


if __name__ == "__main__":
    main()
