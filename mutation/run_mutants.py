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
    # (from round 4 the snippet names the network conduit line: the tide code added
    #  a second conduit, the sump outlet, that uses the same roughness expression)
    ("M20", "sgdrain/swmm_model.py",
     "add(f\"{r.id}  {r.frm}  {r.to}  {_fmt(r.length, 2)}  {cop.MANNING_N['concrete']}\"",
     "add(f\"{r.id}  {r.frm}  {r.to}  {_fmt(r.length, 2)}  0.013\"",
     "SWMM conduits use n = 0.013 instead of the COP 0.015"),
]

# Bugs in the tide / sea-level code (added with the tide/SLR stress test).
TIDE_MUTANTS = [
    ("T01", "sgdrain/coastal.py", "return z_local - outfall_ground_local + outfall_ground_shd",
     "return z_local + outfall_ground_local - outfall_ground_shd", "local-to-SHD offset applied with the wrong sign"),
    ("T02", "sgdrain/coastal.py", "return h_cd - tide_mean_cd + tide_mean_shd",
     "return h_cd + tide_mean_shd", "Chart Datum heights used as SHD (tide mean not removed)"),
    ("T03", "sgdrain/coastal.py", 'V3_TABLE_5_10["Sultan Shoal"][("SSP5-8.5", 2100)][2]',
     'V3_TABLE_5_10["Sultan Shoal"][("SSP5-8.5", 2100)][0]', "V3 scenario takes the median, not the cited top of range"),
    ("T04", "sgdrain/coastal.py", 'OUTFALL_GROUND_SHD_BASE = MIN_PLATFORM_LEVEL_SHD["southern_coast"]',
     'OUTFALL_GROUND_SHD_BASE = MIN_PLATFORM_LEVEL_SHD["northern_coast"]', "datum anchored on the wrong COP level"),
    ("T05", "sgdrain/tide.py", "(1.0 - math.cos(math.pi * f)) / 2.0", "f",
     "tide interpolated linearly instead of by half cosine"),
    ("T06", "sgdrain/tide.py", "num += 0.5 * (a.height_cd + b.height_cd) * dt", "num += a.height_cd * dt",
     "tide mean uses only the earlier extreme of each interval"),
    ("T07", "sgdrain/tide.py", 'return next(e for e in ev if e.kind == "H" and e.height_cd == top)',
     'return [e for e in ev if e.kind == "H" and e.height_cd == top][-1]', "the latest, not the earliest, of tied high waters"),
    ("T08", "sgdrain/tide.py", "t0 = hw.time - timedelta(minutes=peak_offset_min)", "t0 = hw.time",
     "high water placed at the start of the run, not at the storm peak"),
    ("T09", "sgdrain/backwater.py", "return (n * v) ** 2 / r ** (4.0 / 3.0)", "return (n * v) ** 2 / r ** (2.0 / 3.0)",
     "friction slope with R^(2/3) instead of R^(4/3)"),
    ("T10", "sgdrain/backwater.py", "return (s0 * dx + y + velocity_head(q, b, y) - h_dn",
     "return (-s0 * dx + y + velocity_head(q, b, y) - h_dn", "bed slope sign reversed in the energy balance"),
    ("T11", "sgdrain/backwater.py", 'y_dn = max(yn, wl_node[r.to] - inv[r.id]["inv_dn"])',
     'y_dn = max(yn, wl_node[r.to] - inv[r.id]["inv_up"])', "downstream depth measured from the wrong invert"),
    ("T12", "sgdrain/backwater.py", "fb_limit = (1.0 - cop.FREEBOARD_FRACTION) * d", "fb_limit = d",
     "backwater check ignores the COP freeboard (only overtopping)"),
    ("T13", "sgdrain/backwater.py", 'wl_node[r.frm] = p["wl_up"]', 'wl_node[r.frm] = p["inv"][-1] + p["yn"]',
     "junction level not passed upstream (backwater stops at a node)"),
    ("T14", "sgdrain/backwater.py", "        if ok(mid):", "        if not ok(mid):",
     "bisection for the highest tolerable outfall level runs the wrong way"),
    ("T15", "sgdrain/backwater.py",
     "p = network_profile(net, trial, rational.inverts(net, trial), flows, tailwater)",
     "p = network_profile(net, trial, rational.inverts(net, cur), flows, tailwater)",
     "upsizing keeps the old inverts (a deeper drain's cope rises above ground)"),
    ("T16", "sgdrain/backwater.py", "if dz >= tol:", "if dz >= -tol:",
     "backwater extent counts stations that are not raised"),
    ("T17", "sgdrain/pumpsump.py", "s = max(0.0, s + 0.5 * (e0 + e1) * dt)", "s = s + 0.5 * (e0 + e1) * dt",
     "sump storage allowed to go below empty"),
    ("T18", "sgdrain/pumpsump.py", "tc = dt * e0 / (e0 - e1)", "tc = 0.5 * dt",
     "inflow assumed to cross the pump rate mid-step"),
    ("T19", "sgdrain/swmm_model.py", 'gate = "YES" if bc.get("gated") else "NO"', 'gate = "NO"',
     "flap gate dropped from the SWMM outfall"),
    ("T20", "sgdrain/swmm_model.py", "y0 = _fmt(min(max(0.0, init_level - node_inv[nid]), ymax))", 'y0 = "0"',
     "open outfall: drains not pre-filled to the tide level"),
    ("T21", "sgdrain/tide_pipeline.py",
     '"d_flood_m3": round(res.total_flood_volume_m3 - res0.total_flood_volume_m3, 1),',
     '"d_flood_m3": round(res.total_flood_volume_m3, 1),', "extra overtopping not measured against the free outfall"),
    ("T22", "sgdrain/tide_pipeline.py", 'coastal.cd_to_shd(h, ctx["mean_cd"]) + slr',
     'coastal.cd_to_shd(h, ctx["mean_cd"]) - slr', "sea-level rise subtracted"),
    ("T23", "sgdrain/tide_pipeline.py",
     'return [(t, ctx["of_ground_local"] + hw_rel_ground + (h - top)) for t, h in ctx["curve_cd"]]',
     'return [(t, ctx["of_ground_local"] + hw_rel_ground) for t, h in ctx["curve_cd"]]',
     "sweep loses the tide curve (flat sea at high water)"),
    ("T24", "sgdrain/tide_pipeline.py", "return (k + 0.5) * dt_min", "return k * dt_min",
     "storm peak taken at the start of the peak block"),
    ("T25", "sgdrain/tide_pipeline.py", "    if not gated:", "    if gated:",
     "drains pre-filled behind the flap gate instead of the open outfall"),
    ("T26", "sgdrain/tide_pipeline.py", "rise = {n: head[n] - head0[n] for n in head if n != of}",
     "rise = {n: head[n] - head0[n] for n in head}", "the outfall boundary node counted as raised by the tide"),
]
MUTANTS = MUTANTS + TIDE_MUTANTS


def group_of(mid: str) -> str:
    return "tide" if mid.startswith("T") else "design"

# "local": data/local holds the tide table that is not redistributed; mutants must be killed
# by what a clean checkout has, so the scratch copy leaves it out.
IGNORE = shutil.ignore_patterns(".venv", ".git", "__pycache__", ".pytest_cache", "_work",
                                "*.rpt", "*.out", "*.pdf", "local")


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


def group_stats(results: list[dict]) -> dict:
    out = {}
    for g in ("design", "tide"):
        rs = [r for r in results if group_of(r["id"]) == g]
        if rs:
            out[g] = {"n": len(rs), "n_killed": sum(r["status"] == "killed" for r in rs),
                      "survivors": [f"{r['id']} ({r['description']})" for r in rs
                                    if r["status"] == "survived"]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", choices=["design", "tide"], default=None,
                    help="run one group and print the result without writing the report")
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

    todo = [mm for mm in MUTANTS if args.only is None or group_of(mm[0]) == args.only]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_mutant, todo))
    for r in results:
        print(f"{r['id']} {r['status']:<9} {r['description']}  [{r.get('first_failing_test')}]")
    if args.only:
        gs = group_stats(results)[args.only]
        print(f"[{args.only} only, report not written] killed {gs['n_killed']}/{gs['n']}; "
              f"survivors: {gs['survivors']}")
        return

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
        "groups": group_stats(results),
        "mutants": results,
    }
    out_path = REPO / "results" / "mutation_report.json"
    # keep the history of earlier rounds (tests are strengthened between rounds)
    history = []
    if out_path.exists():
        prev = json.loads(out_path.read_text())
        history = prev.get("history") or [{
            "round": 1, "baseline_passed": prev["baseline_passed"],
            "n_mutants": prev["n_mutants"], "n_killed": prev["n_killed"],
            "survivors": prev["survivors"]}]
    report["history"] = history + [{
        "round": len(history) + 1, "baseline_passed": baseline,
        "n_mutants": report["n_mutants"], "n_killed": report["n_killed"],
        "survivors": report["survivors"], "groups": report["groups"]}]
    report["round"] = len(report["history"])
    # the first round that included the tide/sea-level mutants
    first_tide = next((h for h in report["history"] if "tide" in h.get("groups", {})), None)
    if first_tide is not None:
        report["tide_first_round"] = {"round": first_tide["round"],
                                      "baseline_passed": first_tide["baseline_passed"],
                                      **first_tide["groups"]["tide"]}
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    sys.path.insert(0, str(REPO))
    from sgdrain import readme
    readme.write()
    print(f"killed {report['n_killed']}/{report['n_mutants']}; report -> results/mutation_report.json")


if __name__ == "__main__":
    main()
