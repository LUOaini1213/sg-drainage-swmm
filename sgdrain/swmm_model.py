"""Build, run and read an EPA SWMM 5 model of the designed network.

The engine is the official SWMM 5.2 solver shipped in the ``swmm-toolkit``
wheel (``swmm.toolkit.solver.swmm_run``).  Results are read from the text
report (.rpt) summary tables, which SWMM always writes.

Hydrology parameters (assumptions, sources in docs/sources.md):
  * %impervious: roads 100 %, built-up "urban" plots 90 %, vegetated 0 %;
  * width = area / overland flow length (per land-use type);
  * N-imperv 0.011 (smooth asphalt), N-perv 0.15 (short grass)
    -- SWMM 5.2 User's Manual, Table A.6;
  * depression storage 1.27 mm impervious / 2.54 mm pervious -- lower ends
    of Table A.5 (0.05 in / 0.10 in);
  * %Zero-Imperv 25 -- the manual's default in its Section 2.2 example;
  * Green-Ampt, clay loam (Table A.2): suction 8.27 in, Ksat 0.04 in/hr,
    initial deficit = porosity - field capacity = 0.464 - 0.310.
Hydraulics: dynamic wave, open rectangular conduits (RECT_OPEN) with the
COP concrete n = 0.015, invert elevations from ``rational.inverts``, free
outfall, no ponding (water above the drain cope at a node is reported as
flooding and lost).

Outfall boundary (``build_inp(..., outfall=...)``, default free):
  * ``{"type": "FIXED", "stage": z}`` or ``{"type": "TIMESERIES", "series":
    [(minutes, z), ...]}`` - the sea level at the outfall (SWMM uses the
    larger of that level and critical/normal depth), optional
    ``"gated": True`` for a flap gate that stops backflow, and optional
    ``"init_level": z`` to start the drains filled to the tide level;
  * ``{"type": "PUMPED", "stage" or "series", "pump_m3s": Qp,
    "sump_area_m2": A}`` - the outfall node becomes a sump (storage of plan
    area A, floor at the outfall invert) that drains to the sea through a
    flap-gated outlet and is emptied by a pump of capacity Qp (SWMM PUMP4
    curve: flow rises to Qp over the first 0.05 m of sump depth).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import cop
from .network import Network

IN_PER_MM = 1 / 25.4

HYDROLOGY = {
    "impervious_fraction": {"road": 1.00, "urban": 0.90, "vegetated": 0.00},
    "n_imperv": 0.011,
    "n_perv": 0.15,
    "dstore_imperv_mm": round(0.05 * 25.4, 2),
    "dstore_perv_mm": round(0.10 * 25.4, 2),
    "pct_zero_imperv": 25,
    "ga_suction_mm": round(8.27 * 25.4, 1),
    "ga_ksat_mm_hr": round(0.04 * 25.4, 3),
    "ga_initial_deficit": round(0.464 - 0.310, 3),
}

OPTIONS = {
    "routing_step_s": 1,
    "report_step": "00:01:00",
    "sim_hours": 4,
}


def pct_impervious(fractions: dict) -> float:
    f = HYDROLOGY["impervious_fraction"]
    return 100.0 * sum(f[k] * v for k, v in fractions.items())


def _fmt(x: float, nd: int = 4) -> str:
    return f"{x:.{nd}f}"


PUMP_RAMP_DEPTH_M = 0.05      # sump depth over which the pump reaches capacity
GATE_CONDUIT_LENGTH_M = 10.0  # flap-gated outlet from the sump to the sea
OUTFALL_TYPES = ("FREE", "FIXED", "TIMESERIES", "PUMPED")


def _hm(minutes: float) -> str:
    m = int(round(minutes))
    return f"{m // 60}:{m % 60:02d}"


def _stage_spec(bc: dict) -> str:
    """Stage part of an [OUTFALLS] line for a FIXED or TIMESERIES sea level."""
    if "series" in bc:
        return "TIMESERIES  TIDE"
    return f"FIXED  {_fmt(bc['stage'])}"


def build_inp(net: Network, secs: dict, inv: dict, hyeto_mm_hr: list[float],
              dt_min: int, title: str, *, outfall: dict | None = None,
              report_series: bool = False) -> str:
    """Return the text of a SWMM .inp file.

    ``outfall`` sets the outfall boundary (see the module docstring; None =
    free outfall).  ``report_series`` writes every node and link to the
    binary output so that time series can be read back (``run_inp_series``).
    """
    bc = dict(outfall or {"type": "FREE"})
    kind = bc.get("type", "FREE")
    if kind not in OUTFALL_TYPES:
        raise ValueError(f"unknown outfall type {kind}")
    if kind in ("FIXED", "PUMPED") and "stage" not in bc and "series" not in bc:
        raise ValueError(f"{kind} outfall needs a stage or a series")
    if kind == "TIMESERIES" and "series" not in bc:
        raise ValueError("TIMESERIES outfall needs a series")
    gate = "YES" if bc.get("gated") else "NO"
    init_level = bc.get("init_level")
    h = HYDROLOGY
    L: list[str] = []
    add = L.append
    add("[TITLE]")
    add(title)
    add("SYNTHETIC catchment - screening model, not a PUB-approved design")
    add("")
    add("[OPTIONS]")
    for k, v in [("FLOW_UNITS", "CMS"), ("INFILTRATION", "GREEN_AMPT"),
                 ("FLOW_ROUTING", "DYNWAVE"), ("LINK_OFFSETS", "ELEVATION"),
                 ("MIN_SLOPE", "0"), ("ALLOW_PONDING", "NO"),
                 ("SKIP_STEADY_STATE", "NO"),
                 ("START_DATE", "01/01/2026"), ("START_TIME", "00:00:00"),
                 ("REPORT_START_DATE", "01/01/2026"), ("REPORT_START_TIME", "00:00:00"),
                 ("END_DATE", "01/01/2026"),
                 ("END_TIME", f"{OPTIONS['sim_hours']:02d}:00:00"),
                 ("SWEEP_START", "01/01"), ("SWEEP_END", "12/31"), ("DRY_DAYS", "0"),
                 ("REPORT_STEP", OPTIONS["report_step"]), ("WET_STEP", "00:01:00"),
                 ("DRY_STEP", "00:05:00"),
                 ("ROUTING_STEP", str(OPTIONS["routing_step_s"])),
                 ("INERTIAL_DAMPING", "PARTIAL"), ("NORMAL_FLOW_LIMITED", "BOTH"),
                 ("FORCE_MAIN_EQUATION", "H-W"), ("VARIABLE_STEP", "0.75"),
                 ("LENGTHENING_STEP", "0"), ("MIN_SURFAREA", "1.167"),
                 ("MAX_TRIALS", "8"), ("HEAD_TOLERANCE", "0.0015"),
                 ("SYS_FLOW_TOL", "5"), ("LAT_FLOW_TOL", "5"), ("THREADS", "1")]:
        add(f"{k:<22}{v}")
    add("")
    add("[RAINGAGES]")
    add(f"RG1  INTENSITY  0:{dt_min:02d}  1.0  TIMESERIES  DESIGN_STORM")
    add("")
    add("[SUBCATCHMENTS]")
    for s in net.subcatchments:
        area_m2 = s.area_ha * 10_000
        width = area_m2 / s.overland_length_m
        add(f"{s.id}  RG1  {s.outlet}  {_fmt(s.area_ha)}  {_fmt(pct_impervious(s.fractions), 2)}"
            f"  {_fmt(width, 2)}  {_fmt(s.slope_pct, 2)}  0")
    add("")
    add("[SUBAREAS]")
    for s in net.subcatchments:
        add(f"{s.id}  {h['n_imperv']}  {h['n_perv']}  {h['dstore_imperv_mm']}"
            f"  {h['dstore_perv_mm']}  {h['pct_zero_imperv']}  OUTLET")
    add("")
    add("[INFILTRATION]")
    for s in net.subcatchments:
        add(f"{s.id}  {h['ga_suction_mm']}  {h['ga_ksat_mm_hr']}  {h['ga_initial_deficit']}")
    add("")
    # node invert = lowest drain invert at the node; node max depth = highest
    # drain cope at the node (SWMM raises a node's max depth to the highest
    # connecting crown anyway).  Water above it is reported as flooding.
    node_inv: dict[str, float] = {}
    node_cope: dict[str, float] = {}
    for r in net.reaches:
        b, d, _ = secs[r.id]
        for nid, inv_key in ((r.frm, "inv_up"), (r.to, "inv_dn")):
            node_inv[nid] = min(node_inv.get(nid, 1e9), inv[r.id][inv_key])
            node_cope[nid] = max(node_cope.get(nid, -1e9), inv[r.id][inv_key] + d)
    add("[JUNCTIONS]")
    for nid, n in net.nodes.items():
        if n.outfall:
            continue
        ymax = node_cope[nid] - node_inv[nid]
        if init_level is None:
            y0 = "0"
        else:
            y0 = _fmt(min(max(0.0, init_level - node_inv[nid]), ymax))
        add(f"{nid}  {_fmt(node_inv[nid])}  {_fmt(ymax)}  {y0}  0  0")
    add("")
    outfall_ids = [nid for nid, n in net.nodes.items() if n.outfall]
    if len(outfall_ids) != 1:
        raise ValueError("the network must have exactly one outfall")
    of = outfall_ids[0]
    of_reach = next(r for r in net.reaches if r.to == of)
    of_b, of_d, _ = secs[of_reach.id]
    add("[OUTFALLS]")
    if kind == "FREE":
        add(f"{of}  {_fmt(node_inv[of])}  FREE  {gate}")
    elif kind in ("FIXED", "TIMESERIES"):
        add(f"{of}  {_fmt(node_inv[of])}  {_stage_spec(bc)}  {gate}")
    else:  # PUMPED: the sea sits behind a flap-gated outlet; the pump lifts over the wall
        add(f"SEA  {_fmt(node_inv[of])}  {_stage_spec(bc)}  YES")
        add(f"SEA_P  {_fmt(node_cope[of])}  FREE  NO")
    add("")
    if kind == "PUMPED":
        add("[STORAGE]")
        # constant plan area A: FUNCTIONAL area = A1 * depth^A2 + A0 with A1 = A2 = 0
        add(f"{of}  {_fmt(node_inv[of])}  {_fmt(node_cope[of] - node_inv[of])}  0  FUNCTIONAL"
            f"  0  0  {_fmt(bc['sump_area_m2'], 1)}  0  0")
        add("")
    add("[CONDUITS]")
    for r in net.reaches:
        add(f"{r.id}  {r.frm}  {r.to}  {_fmt(r.length, 2)}  {cop.MANNING_N['concrete']}"
            f"  {_fmt(inv[r.id]['inv_up'])}  {_fmt(inv[r.id]['inv_dn'])}  0  0")
    if kind == "PUMPED":
        add(f"GATE  {of}  SEA  {_fmt(GATE_CONDUIT_LENGTH_M, 2)}  {cop.MANNING_N['concrete']}"
            f"  {_fmt(node_inv[of])}  {_fmt(node_inv[of])}  0  0")
    add("")
    if kind == "PUMPED":
        add("[PUMPS]")
        add(f"PUMP1  {of}  SEA_P  PCURVE  ON  0  0")
        add("")
        add("[CURVES]")
        add("PCURVE  PUMP4  0  0")
        add(f"PCURVE  {PUMP_RAMP_DEPTH_M}  {_fmt(bc['pump_m3s'])}")
        add(f"PCURVE  {_fmt(node_cope[of] - node_inv[of] + 1.0)}  {_fmt(bc['pump_m3s'])}")
        add("")
    add("[XSECTIONS]")
    for r in net.reaches:
        b, d, _ = secs[r.id]
        add(f"{r.id}  RECT_OPEN  {d}  {b}  0  0  1")
    if kind == "PUMPED":
        add(f"GATE  RECT_OPEN  {of_d}  {of_b}  0  0  1")
    add("")
    add("[TIMESERIES]")
    for k, v in enumerate(hyeto_mm_hr):
        t = k * dt_min
        add(f"DESIGN_STORM  {t // 60}:{t % 60:02d}  {_fmt(v, 3)}")
    t = len(hyeto_mm_hr) * dt_min
    add(f"DESIGN_STORM  {t // 60}:{t % 60:02d}  0.000")
    if "series" in bc and kind != "FREE":
        for tm, z in bc["series"]:
            add(f"TIDE  {_hm(tm)}  {_fmt(z)}")
    add("")
    add("[REPORT]")
    add("INPUT NO")
    add("CONTINUITY YES")
    add("FLOWSTATS YES")
    add("CONTROLS NO")
    if report_series:
        add("NODES ALL")
        add("LINKS ALL")
    add("")
    add("[COORDINATES]")
    for nid, n in net.nodes.items():
        add(f"{nid}  {_fmt(n.x, 1)}  {_fmt(n.y, 1)}")
    if kind == "PUMPED":
        n = net.nodes[of]
        add(f"SEA  {_fmt(n.x + 20, 1)}  {_fmt(n.y, 1)}")
        add(f"SEA_P  {_fmt(n.x + 20, 1)}  {_fmt(n.y + 15, 1)}")
    add("")
    add("[Polygons]")
    for s in net.subcatchments:
        x0, y0, x1, y1 = s.rect
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            add(f"{s.id}  {x}  {y}")
    add("")
    return "\n".join(L) + "\n"


@dataclass
class SwmmResult:
    runoff_continuity_pct: float
    routing_continuity_pct: float
    subcatchments: dict  # id -> {peak_runoff, runoff_coeff, infil_mm, runoff_mm}
    links: dict      # id -> {max_flow, max_velocity, max_over_full_flow, max_over_full_depth}
    nodes: dict      # id -> {max_depth, max_hgl, hours_flooded, flood_volume_m3, max_flood_rate}
    total_flood_volume_m3: float
    total_precip_mm: float
    runoff_coefficient: float
    warnings: list
    pumps: dict = field(default_factory=dict)   # id -> {type, max_flow}


def run_inp(inp_path: Path) -> SwmmResult:
    from swmm.toolkit import solver
    inp_path = Path(inp_path)
    rpt = inp_path.with_suffix(".rpt")
    out = inp_path.with_suffix(".out")
    solver.swmm_run(str(inp_path), str(rpt), str(out))
    return parse_rpt(rpt.read_text(errors="replace"))


def run_inp_series(inp_path: Path, links=(), nodes=()) -> tuple[SwmmResult, dict]:
    """Run the model, parse the report, and read time series from the binary
    output: flow (m3/s) of ``links`` and hydraulic head (m) of ``nodes``.
    The .inp must have been built with ``report_series=True``.  Values are
    at the end of each reporting step (t_s = step, 2 * step, ...)."""
    from swmm.toolkit import output, shared_enum
    inp_path = Path(inp_path)
    res = run_inp(inp_path)
    h = output.init()
    output.open(h, str(inp_path.with_suffix(".out")))
    try:
        n_per = output.get_times(h, shared_enum.Time.NUM_PERIODS)
        step = output.get_times(h, shared_enum.Time.REPORT_STEP)
        _, n_nodes, n_links = output.get_proj_size(h)[:3]
        node_names = [output.get_elem_name(h, shared_enum.ElementType.NODE, k) for k in range(n_nodes)]
        link_names = [output.get_elem_name(h, shared_enum.ElementType.LINK, k) for k in range(n_links)]
        series = {"t_s": [step * (k + 1) for k in range(n_per)], "link_flow": {}, "node_head": {}}
        for lid in links:
            series["link_flow"][lid] = list(output.get_link_series(
                h, link_names.index(lid), shared_enum.LinkAttribute.FLOW_RATE, 0, n_per - 1))
        for nid in nodes:
            series["node_head"][nid] = list(output.get_node_series(
                h, node_names.index(nid), shared_enum.NodeAttribute.HYDRAULIC_HEAD, 0, n_per - 1))
    finally:
        output.close(h)
    return res, series


def _section(text: str, title: str) -> list[str]:
    """Data rows of a report summary table ([] if SWMM printed a 'No ...'
    message instead of the table)."""
    i = text.find(title)
    if i < 0:
        return []
    lines = text[i:].splitlines()[1:]
    k = 0
    # skip the asterisk underline and blank lines
    while k < len(lines) and (not lines[k].strip() or set(lines[k].strip()) == {"*"}):
        k += 1
    head = lines[k:k + 12]
    if not head or not any(ln.strip().startswith("---") for ln in head):
        return []
    if any(ln.strip().startswith("No ") for ln in lines[k:k + 3]):
        return []
    dashes = [j for j, ln in enumerate(head) if ln.strip().startswith("---")]
    start = k + dashes[-1] + 1
    rows = []
    for ln in lines[start:]:
        if not ln.strip():
            break
        rows.append(ln)
    return rows


def parse_rpt(text: str) -> SwmmResult:
    errs = re.findall(r"Continuity Error \(%\) \.+\s+(-?[\d.]+)", text)
    if len(errs) < 2:
        raise RuntimeError("SWMM report has no continuity errors - run failed?\n" + text[-2000:])
    m = re.search(r"Total Precipitation \.+\s+[\d.]+\s+([\d.]+)", text)
    total_precip = float(m.group(1)) if m else float("nan")
    links = {}
    pumps = {}
    for ln in _section(text, "Link Flow Summary"):
        p = ln.split()
        if p[1] != "CONDUIT":       # a pump row has no velocity or depth columns
            pumps[p[0]] = {"type": p[1], "max_flow": float(p[2])}
            continue
        # Name Type MaxFlow Day hr:min MaxVeloc MaxFull/Flow MaxFull/Depth
        links[p[0]] = {"max_flow": float(p[2]), "max_velocity": float(p[5]),
                       "max_over_full_flow": float(p[6]), "max_over_full_depth": float(p[7])}
    nodes = {}
    for ln in _section(text, "Node Depth Summary"):
        p = ln.split()
        nodes[p[0]] = {"avg_depth": float(p[2]), "max_depth": float(p[3]),
                       "max_hgl": float(p[4]), "hours_flooded": 0.0,
                       "flood_volume_m3": 0.0, "max_flood_rate": 0.0}
    subs = {}
    for ln in _section(text, "Subcatchment Runoff Summary"):
        p = ln.split()
        subs[p[0]] = {"peak_runoff": float(p[9]), "runoff_coeff": float(p[10]),
                      "infil_mm": float(p[4]), "runoff_mm": float(p[7])}
    for ln in _section(text, "Node Flooding Summary"):
        p = ln.split()
        if p[0] in nodes:
            nodes[p[0]]["hours_flooded"] = float(p[1])
            nodes[p[0]]["max_flood_rate"] = float(p[2])
            # total flood volume is reported in 10^6 litres = 1000 m3
            nodes[p[0]]["flood_volume_m3"] = float(p[5]) * 1000.0
    m = re.search(r"Surface Runoff \.+\s+[\d.]+\s+([\d.]+)", text)
    rc = float(m.group(1)) / total_precip if m and total_precip > 0 else float("nan")
    return SwmmResult(
        runoff_continuity_pct=float(errs[0]),
        routing_continuity_pct=float(errs[1]),
        subcatchments=subs, links=links, nodes=nodes,
        total_flood_volume_m3=sum(n["flood_volume_m3"] for n in nodes.values()),
        total_precip_mm=total_precip, runoff_coefficient=rc,
        warnings=[w.strip() for w in re.findall(r"WARNING.*", text)],
        pumps=pumps,
    )
