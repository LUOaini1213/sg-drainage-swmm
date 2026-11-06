"""Figures written to results/figures (all drawn from results computed in
pipeline.main - no hand-entered numbers)."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402

from . import cop, idf  # noqa: E402

INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
BLUE = "#2a78d6"        # series 1: rational
ORANGE = "#eb6834"      # series 2: SWMM
AQUA = "#1baf7a"        # series 3
CRITICAL = "#d03b3b"    # status: fails a COP criterion / floods
VIOLET = "#6250d6"      # series 3 (stress storm)
SEQ = LinearSegmentedColormap.from_list(
    "util", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#104281"])
SYNTH = "SYNTHETIC catchment - screening exercise, not a PUB-approved design"

plt.rcParams.update({
    "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK,
    "axes.titlesize": 10, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "svg.hashsalt": "sg-drainage-swmm", "path.simplify": True,
})


def _save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def _plan_panel(ax, net, util: dict, secs: dict, flooded: list, title: str):
    norm = Normalize(0.5, 1.0)
    for s in net.subcatchments:
        x0, y0, x1, y1 = s.rect
        ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="#f0efec",
                                   edgecolor="#d6d5d0", lw=0.8, zorder=0))
        ax.text(x0 + 6, y1 - 6, f"{s.id}\n{s.area_ha:.2f} ha, C={s.c:.2f}", fontsize=6,
                color=MUTED, va="top", ha="left", zorder=1)
    for r in net.reaches:
        a, b = net.nodes[r.frm], net.nodes[r.to]
        u = util[r.id]
        fail = u > 1.0 + 1e-9
        col = CRITICAL if fail else SEQ(norm(u))
        lw = 2 + 3 * secs[r.id][0]
        ax.plot([a.x, b.x], [a.y, b.y], color=SURFACE, lw=lw + 2.5, solid_capstyle="butt", zorder=2)
        ax.plot([a.x, b.x], [a.y, b.y], color=col, lw=lw, solid_capstyle="butt", zorder=3,
                linestyle=(0, (3, 1.2)) if fail else "-")
        mx, my = (a.x + b.x) / 2, (a.y + b.y) / 2
        horiz = abs(b.x - a.x) > abs(b.y - a.y)
        dx, dy = (0, -11) if horiz else (8, 0)
        label = f"{r.id}  {secs[r.id][0]:.1f}x{secs[r.id][1]:.1f}\nU={u:.2f}" + (" FAIL" if fail else "")
        ax.text(mx + dx, my + dy, label, fontsize=6.5, color=CRITICAL if fail else INK,
                ha="center" if horiz else "left", va="top" if horiz else "center", zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none", alpha=0.85))
        # flow arrow
        ax.annotate("", xy=(a.x + 0.62 * (b.x - a.x), a.y + 0.62 * (b.y - a.y)),
                    xytext=(a.x + 0.52 * (b.x - a.x), a.y + 0.52 * (b.y - a.y)),
                    arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.8), zorder=4)
    for nid, n in net.nodes.items():
        fl = nid in flooded
        ax.scatter([n.x], [n.y], s=46 if fl else 18, marker="^" if fl else "o",
                   facecolor=CRITICAL if fl else SURFACE, edgecolor=CRITICAL if fl else INK,
                   lw=1.0, zorder=6)
        ax.text(n.x - 5, n.y + 6, nid, fontsize=6.5, color=INK2, ha="right", va="bottom", zorder=6)
    ax.set_aspect("equal")
    ax.set_xlim(-25, 445)
    ax.set_ylim(-20, 318)
    ax.set_title(title, loc="left")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(False)


def plan(net, design, secs, base_swmm, stress, path: Path):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))
    u0 = {r.reach: r.utilisation for r in design}
    _plan_panel(axes[0], net, u0, secs, base_swmm["design"]["flooded_nodes"],
                "(a) Design storm, 10-yr: rational utilisation Qr/Qc")
    t = stress["t100"]
    u1 = {row["reach"]: row["utilisation_existing"] for row in t["_rows"]}
    _plan_panel(axes[1], net, u1, secs, t["swmm_existing"]["flooded_nodes"],
                "(b) 100-yr storm on the same drains")
    handles = [
        Line2D([], [], color=SEQ(0.25), lw=4, label="utilisation 0.5-1.0 (darker = fuller)"),
        Line2D([], [], color=CRITICAL, lw=4, ls=(0, (3, 1.2)), label="FAIL: utilisation > 1 (into COP freeboard)"),
        Line2D([], [], marker="^", color="none", markerfacecolor=CRITICAL, markeredgecolor=CRITICAL,
               markersize=7, label="node overtopped in SWMM"),
        Line2D([], [], marker="o", color="none", markerfacecolor=SURFACE, markeredgecolor=INK,
               markersize=5, label="node / junction"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8)
    fig.suptitle("Drain network plan - reach ID, internal width x depth (m), utilisation", x=0.01,
                 ha="left", fontsize=11, color=INK)
    fig.text(0.99, 0.985, SYNTH, ha="right", va="top", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    _save(fig, path)


def long_section(net, design, secs, inv, base_res, t100_res, path: Path):
    main = net.main_line()
    by = {r.reach: r for r in design}
    ch, x = {}, 0.0
    for r in main:
        ch[r.frm] = x
        x += r.length
        ch[r.to] = x
    fig, ax = plt.subplots(figsize=(11, 4.6))
    xs_g = [ch[r.frm] for r in main] + [ch[main[-1].to]]
    gs = [net.nodes[r.frm].ground for r in main] + [net.nodes[main[-1].to].ground]
    ax.plot(xs_g, gs, color="#8b6b3d", lw=1.6, label="ground (synthetic)")
    first = True
    for r in main:
        x0, x1 = ch[r.frm], ch[r.to]
        lv = inv[r.id]
        y = by[r.id].y_m
        ax.fill_between([x0, x1], [lv["inv_up"], lv["inv_dn"]], [lv["cope_up"], lv["cope_dn"]],
                        color="#e8e7e3", lw=0, zorder=0)
        ax.plot([x0, x1], [lv["inv_up"], lv["inv_dn"]], color=INK, lw=1.6,
                label="drain invert" if first else None)
        ax.plot([x0, x1], [lv["cope_up"], lv["cope_dn"]], color=INK2, lw=0.9, ls="--",
                label="drain cope (top)" if first else None)
        fb = cop.FREEBOARD_FRACTION * secs[r.id][1]
        ax.plot([x0, x1], [lv["cope_up"] - fb, lv["cope_dn"] - fb], color=MUTED, lw=0.8, ls=":",
                label="cope - COP freeboard (15% D)" if first else None)
        ax.plot([x0, x1], [lv["inv_up"] + y, lv["inv_dn"] + y], color=BLUE, lw=2,
                label="rational design water level (normal depth)" if first else None)
        ax.text((x0 + x1) / 2, lv["inv_dn"] - 0.08, f"{r.id}  {secs[r.id][0]:.1f}x{secs[r.id][1]:.1f} m"
                f"  S=1:{1 / r_slope(r.id, secs):.0f}", ha="center", va="top", fontsize=7, color=INK2)
        first = False
    nodes = [r.frm for r in main] + [main[-1].to]
    ax.plot([ch[n] for n in nodes], [base_res.nodes[n]["max_hgl"] for n in nodes], color=ORANGE,
            lw=1.6, marker="o", ms=5, label="SWMM max water level, 10-yr design storm")
    ax.plot([ch[n] for n in nodes], [t100_res.nodes[n]["max_hgl"] for n in nodes], color=VIOLET,
            lw=1.2, marker="^", ms=6, ls="-.", label="SWMM max water level, 100-yr storm (same drains)")
    for n in nodes:
        ax.annotate(n, (ch[n], net.nodes[n].ground + 0.12), ha="center", fontsize=8, color=INK)
        ax.axvline(ch[n], color=GRID, lw=0.8, zorder=-1)
    ax.set_xlabel("chainage along main drain J1 -> OF (m)")
    ax.set_ylabel("level (m, local datum)")
    ax.set_title("Long-section of the main drain (M1-M4)", loc="left")
    ax.legend(loc="upper right", fontsize=7.5, ncol=2)
    ax.set_ylim(min(lv["inv_dn"] for lv in inv.values()) - 0.4,
                max(gs) + 0.55)
    fig.text(0.99, 0.01, SYNTH, ha="right", va="bottom", fontsize=7, color=MUTED)
    fig.tight_layout()
    _save(fig, path)


def r_slope(rid, secs):
    return secs[rid][2]


def idf_plot(design, path: Path):
    durations, table = idf.load_table()
    fig, ax = plt.subplots(figsize=(7, 4.6))
    order = [100, 50, 25, 15, 10, 5, 3, 2]
    shades = ["#0d366b", "#104281", "#184f95", "#1c5cab", BLUE, "#5598e7", "#86b6ef", "#b7d3f6"]
    for T, c in zip(order, shades):
        lw = 2.2 if T == 10 else 1.1
        ax.plot(durations, table[T], color=c, lw=lw)
        ax.text(durations[-1] * 1.04, table[T][-1], f"{T}-yr", fontsize=7, va="center", color=INK2)
    out = design[-1]
    ax.scatter([r.tc_min for r in design], [r.intensity_mm_hr for r in design], s=16,
               color=ORANGE, zorder=5, label="design points (tc, I) of the 11 reaches")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(4, 1000)
    ax.set_xlabel("duration (min)")
    ax.set_ylabel("intensity (mm/hr)")
    ax.set_title("IDF curves digitised from COP Appendix 4 (Singapore Island)", loc="left")
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(True, which="both", color=GRID, lw=0.5)
    fig.text(0.99, 0.01, "values digitised by tools/digitize_idf.py; see data/", ha="right",
             fontsize=7, color=MUTED)
    fig.tight_layout()
    _save(fig, path)
    _ = out


def hyeto_plot(csv_path: Path, path: Path):
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    t = [float(r["start_min"]) for r in rows]
    dt = t[1] - t[0]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar([x + dt / 2 for x in t], [float(r["design_10yr"]) for r in rows], width=dt * 0.9,
           color=BLUE, label="10-yr design storm (alternating block)")
    for key, col, ls, lab in (("t100", ORANGE, "-", "100-yr"),
                              ("cc_v3_high", VIOLET, "--", "10-yr +92% (V3 high end)")):
        ys = [float(r[key]) for r in rows]
        ax.step(t + [t[-1] + dt], ys + [ys[-1]], where="post", color=col, lw=1.4, ls=ls, label=lab)
    ax.set_xlabel("time from storm start (min)")
    ax.set_ylabel("rainfall intensity (mm/hr)")
    ax.set_title("Design and stress hyetographs (5-min blocks, 120-min storms)", loc="left")
    ax.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, path)


def swmm_vs_rational(csv_path: Path, path: Path):
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ids = [r["reach"] for r in rows]
    y = list(range(len(ids)))[::-1]
    rq = [float(r["rational_q_m3s"]) for r in rows]
    sq = [float(r["swmm_peak_m3s"]) for r in rows]
    for yy, a, b in zip(y, rq, sq):
        ax.plot([a, b], [yy, yy], color=GRID, lw=3, zorder=1)
    ax.scatter(rq, y, color=BLUE, s=36, zorder=3, label="rational Qr (COP Cl. 7.1.1)")
    ax.scatter(sq, y, color=ORANGE, s=36, zorder=3, label="SWMM peak, 10-yr alternating-block storm")
    for yy, a, b in zip(y, rq, sq):
        ax.text(b * 1.03 + 0.05, yy, f"x{b / a:.2f}", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(ids)
    ax.set_xlabel("peak flow (m3/s)")
    ax.set_title("SWMM peak vs rational design flow, per reach", loc="left")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    _save(fig, path)


def sweep_plot(rat_csv: Path, swmm_csv: Path, path: Path):
    with open(rat_csv) as f:
        rat = list(csv.DictReader(f))
    with open(swmm_csv) as f:
        sw = list(csv.DictReader(f))
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    ax = axes[0]
    ax.step([int(r["uplift_pct"]) for r in rat], [int(r["n_failing"]) for r in rat], where="post",
            color=BLUE, lw=2)
    ax.set_xlabel("uplift on 10-yr intensity (%)")
    ax.set_ylabel("reaches failing a COP criterion")
    ax.set_title("(a) Rational check of the design sizes", loc="left")
    ax.set_ylim(0, 11.5)
    ax = axes[1]
    ax.plot([int(r["uplift_pct"]) for r in sw], [float(r["flood_volume_m3"]) for r in sw],
            color=ORANGE, lw=2, marker="o", ms=4)
    ax.set_xlabel("uplift on 10-yr intensity (%)")
    ax.set_ylabel("SWMM total overtopping volume (m3)")
    ax.set_title("(b) SWMM check of the design sizes", loc="left")
    for a, yfrac in zip(axes, (0.45, 0.92)):
        a.axvspan(6, 92, color="#f0efec", zorder=-2)
        lo, hi = a.get_ylim()
        a.text(49, lo + yfrac * (hi - lo), "V3 extreme-daily-rainfall range\n(Apr-May, 6-92%)",
               ha="center", va="top", fontsize=7, color=MUTED)
    fig.tight_layout()
    _save(fig, path)


def make_all(net, design, secs, inv, base_res, stress, outdir: Path):
    import json
    from . import pipeline
    res_dir = outdir.parent
    swmm_sum = json.loads((res_dir / "swmm_summary.json").read_text())
    with open(res_dir / "stress_reaches.csv") as f:
        rows = list(csv.DictReader(f))
    st = dict(stress)
    st["t100"] = dict(st["t100"])
    st["t100"]["_rows"] = [{"reach": r["reach"], "utilisation_existing": float(r["utilisation_existing"])}
                           for r in rows if r["scenario"] == "t100"]
    plan(net, design, secs, swmm_sum, st, outdir / "plan_utilisation.png")
    t100_res, _, _ = pipeline.run_swmm(net, secs, 100, 0.0, "t100_existing", None)
    long_section(net, design, secs, inv, base_res, t100_res, outdir / "long_section_main.png")
    idf_plot(design, outdir / "idf_digitised.png")
    hyeto_plot(res_dir / "hyetographs.csv", outdir / "hyetographs.png")
    swmm_vs_rational(res_dir / "swmm_vs_rational.csv", outdir / "swmm_vs_rational.png")
    sweep_plot(res_dir / "uplift_sweep_rational.csv", res_dir / "uplift_sweep_swmm.csv",
               outdir / "uplift_sweep.png")
