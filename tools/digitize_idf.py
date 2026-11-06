"""Digitise the rainfall IDF curves printed in Appendix 4 of PUB's
Code of Practice on Surface Water Drainage (7th Edition, Dec 2018, with
amendments under Addendum No. 3, April 2025).

The COP gives the IDF relationship only as a raster chart (Appendix 4,
printed page 49 / PDF page 68).  This tool reads the embedded chart image
from a locally downloaded copy of the COP PDF, calibrates both log axes from
the detected grid lines, traces the eight return-period curves column by
column and writes the digitised intensities to ``data/``.

The COP PDF itself is NOT redistributed with this repository.  Download it
from PUB (see docs/sources.md) and run:

    python tools/digitize_idf.py path/to/Code-of-Practice-on-Surface-Water-Drainage.pdf

Requires PyMuPDF and Pillow (``requirements-tools.txt``).  The design
pipeline only reads the committed CSV, so CI does not need this tool.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]

# SHA-256 of the COP PDF digitised for the committed CSV (retrieved 2026-11-06).
EXPECTED_SHA256 = "e52ba4f37b5ca127d24d0f5c1c3cbd78c0342e33ce3775e762e478f36bb86d92"
APPENDIX4_PDF_PAGE = 68  # 1-based PDF page; printed page number 49

# Axis values of the full-height / full-width grid lines on the chart, in the
# order they appear (left->right for time, top->bottom for intensity).
TIME_GRID_MIN = [2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90,
                 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
INTENSITY_GRID_MMHR = [500, 400, 300, 200, 100, 90, 80, 70, 60, 50, 40, 30,
                       20, 10, 5]
# Curves from top to bottom on the chart.
RETURN_PERIODS = [100, 50, 25, 15, 10, 5, 3, 2]
# Durations (min) at which intensities are tabulated.
DURATIONS_MIN = [5, 6, 7, 8, 9, 10, 12, 15, 20, 25, 30, 35, 40, 45, 50, 60,
                 75, 90, 105, 120, 150, 180, 240, 300, 360, 480, 600]
# (the curves end near 700 min on the chart; the last few pixels are not
# tabulated because the line ends are not reliable to trace)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_chart(pdf: Path) -> np.ndarray:
    import pymupdf  # imported lazily: only this tool needs it
    from PIL import Image
    import io

    doc = pymupdf.open(pdf)
    page = doc[APPENDIX4_PDF_PAGE - 1]
    if "Appendix 4" not in page.get_text():
        raise SystemExit("PDF page %d is not Appendix 4 - different COP layout?"
                         % APPENDIX4_PDF_PAGE)
    images = page.get_images()
    xref = max(images, key=lambda im: im[2] * im[3])[0]
    pix = pymupdf.Pixmap(doc, xref)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    return np.asarray(img).astype(int)


def _clusters(mask: np.ndarray) -> list[tuple[int, int]]:
    idx = np.where(mask)[0]
    out: list[tuple[int, int]] = []
    if idx.size == 0:
        return out
    start = prev = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i == prev + 1:
            prev = i
            continue
        out.append((start, prev))
        start = prev = i
    out.append((start, prev))
    return out


def detect_grid(im: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return pixel centres of vertical (time) and horizontal (intensity)
    grid lines that span the plotting area."""
    dark = im < 128
    h, w = im.shape
    colfrac = dark[int(0.06 * h):int(0.88 * h), :].mean(axis=0)
    rowfrac = dark[:, int(0.11 * w):int(0.92 * w)].mean(axis=1)
    cols = [(a + b) / 2 for a, b in _clusters(colfrac > 0.5)]
    rows = [(a + b) / 2 for a, b in _clusters(rowfrac > 0.9)]
    # Drop the outer frame / axis lines: keep the run of lines whose count
    # matches the expected grid.
    cols = _select_run(cols, len(TIME_GRID_MIN), ratio_check=True)
    rows = _select_run(rows, len(INTENSITY_GRID_MMHR), ratio_check=False)
    return np.array(cols), np.array(rows)


def _select_run(pos: list[float], n: int, ratio_check: bool) -> list[float]:
    """Pick the n consecutive positions that best fit a log axis."""
    best = None
    vals = TIME_GRID_MIN if ratio_check else INTENSITY_GRID_MMHR
    logv = np.log10(np.array(vals, float))
    for s in range(0, len(pos) - n + 1):
        p = np.array(pos[s:s + n])
        coef = np.polyfit(logv, p, 1)
        res = np.abs(np.polyval(coef, logv) - p).max()
        if best is None or res < best[0]:
            best = (res, list(p))
    if best is None or best[0] > 8:
        raise SystemExit("grid detection failed (residual %s px)" %
                         (None if best is None else round(best[0], 1)))
    return best[1]


class Axes:
    def __init__(self, xg: np.ndarray, yg: np.ndarray):
        self.xg, self.yg = xg, yg
        self.lx = np.log10(np.array(TIME_GRID_MIN, float))
        self.ly = np.log10(np.array(INTENSITY_GRID_MMHR, float))

    def x_of_t(self, t):
        return np.interp(np.log10(t), self.lx, self.xg)

    def t_of_x(self, x):
        return 10 ** np.interp(x, self.xg, self.lx)

    def i_of_y(self, y):
        return 10 ** np.interp(y, self.yg, self.ly)

    def log_axis_residual_px(self) -> dict:
        """Max deviation of grid lines from a single straight log axis
        (a measure of scan distortion; piecewise calibration absorbs it)."""
        out = {}
        for name, v, p in (("time", self.lx, self.xg), ("intensity", self.ly, self.yg)):
            coef = np.polyfit(v, p, 1)
            out[name] = float(np.abs(np.polyval(coef, v) - p).max())
        return out


def trace(im: np.ndarray, ax: Axes, thr: int = 200):
    h, _ = im.shape
    hmask = np.zeros(h, bool)
    for y in ax.yg:
        hmask[int(np.floor(y)) - 3:int(np.ceil(y)) + 4] = True
    vbad = set()
    for g in ax.xg:
        for d in range(-3, 4):
            vbad.add(int(round(g)) + d)
    x_lo = int(round(ax.x_of_t(5))) + 1
    x_hi = int(round(ax.x_of_t(700)))

    def runs(c: int) -> list[float]:
        ymin = int(ax.yg[1])          # below the 400 mm/hr line
        ymax = int(ax.yg[-1]) - 4     # above the 5 mm/hr (bottom) line
        d = (im[:, c] < thr) & ~hmask
        d[:ymin] = False
        d[ymax:] = False
        out = []
        for a, b in _clusters(d):
            if 2 <= b - a + 1 <= 6:
                out.append((a + b) / 2)
        return out

    # anchor: first column right of the 5-min line with exactly 8 curve runs
    # between the 300 and 100 mm/hr lines (all curves are there at short
    # durations, and none is hidden behind a grid line).
    y300 = float(np.interp(np.log10(300), ax.ly[::-1], ax.yg[::-1]))
    y100 = float(np.interp(np.log10(100), ax.ly[::-1], ax.yg[::-1]))
    anchor = None
    for c in range(x_lo, x_lo + 200):
        if c in vbad:
            continue
        r = [y for y in runs(c) if y300 + 3 < y < y100 - 3]
        if len(r) == 8:
            anchor = (c, r)
            break
    if anchor is None:
        raise SystemExit("could not find an anchor column with 8 curves")
    c0, r0 = anchor
    pts = {k: [(c0, r0[k])] for k in range(8)}

    def step(c: int):
        if c in vbad:
            return
        rr = runs(c)
        fwd = c > c0
        preds = [None] * 8
        fresh = [False] * 8
        for k in range(8):
            side = [q for q in pts[k] if (q[0] < c) == fwd]
            near = sorted(side, key=lambda q: abs(q[0] - c))[:15]
            if near and abs(near[0][0] - c) <= 30 and len(near) >= 3:
                xs = np.array([q[0] for q in near], float)
                ys = np.array([q[1] for q in near], float)
                a, b = np.polyfit(xs, ys, 1)
                preds[k] = a * c + b
                fresh[k] = True
        # curves are near-parallel on log-log axes: a curve that has been lost
        # for >30 px is predicted from a fresh neighbour plus their last offset
        for _ in range(8):
            for k in range(8):
                if preds[k] is not None:
                    continue
                for j in (k - 1, k + 1):
                    if 0 <= j < 8 and preds[j] is not None:
                        common = sorted(set(x for x, _ in pts[k]) & set(x for x, _ in pts[j]),
                                        key=lambda x: abs(x - c))
                        if not common:
                            continue
                        x_ref = common[0]
                        yk = dict(pts[k])[x_ref]
                        yj = dict(pts[j])[x_ref]
                        preds[k] = preds[j] + (yk - yj)
                        break
        preds = [p if p is not None else pts[k][-1][1] for k, p in enumerate(preds)]
        preds = np.array(preds)
        for k, y in _ordered_match(rr, preds, tol=2.5):
            pts[k].append((c, y))

    for c in range(c0 + 1, x_hi + 1):
        step(c)
    for c in range(c0 - 1, x_lo - 1, -1):
        step(c)
    return pts


def _ordered_match(runs: list[float], preds: np.ndarray, tol: float):
    """Match runs (sorted top->bottom) to curve predictions without letting
    curves cross: maximise the number of matches within ``tol`` px, then
    minimise total distance.  Returns [(curve_index, y), ...]."""
    n, m = len(runs), len(preds)
    # dp[i][j] = (matches, -cost) best using first i runs and first j curves
    dp = [[(0, 0.0)] * (m + 1) for _ in range(n + 1)]
    choice = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 or j == 0:
                continue
            best, how = dp[i - 1][j], "skip_run"
            if dp[i][j - 1] > best:
                best, how = dp[i][j - 1], "skip_curve"
            d = abs(runs[i - 1] - preds[j - 1])
            if d <= tol:
                cand = (dp[i - 1][j - 1][0] + 1, dp[i - 1][j - 1][1] - d)
                if cand > best:
                    best, how = cand, "match"
            dp[i][j], choice[i][j] = best, how
    out = []
    i, j = n, m
    while i > 0 and j > 0:
        how = choice[i][j]
        if how == "match":
            out.append((j - 1, runs[i - 1]))
            i, j = i - 1, j - 1
        elif how == "skip_run":
            i -= 1
        else:
            j -= 1
    return out


def tabulate(pts, ax: Axes):
    """Local robust linear fit around each tabulated duration."""
    table = {}
    quality = {}
    for k, T in enumerate(RETURN_PERIODS):
        arr = np.array(sorted(pts[k]), float)
        xs, ys = arr[:, 0], arr[:, 1]
        keep = np.ones(len(xs), bool)
        # iterative outlier rejection against a +-25 px local line
        for _ in range(3):
            for j in range(len(xs)):
                w = (np.abs(xs - xs[j]) <= 25) & keep
                if w.sum() < 6:
                    continue
                a, b = np.polyfit(xs[w], ys[w], 1)
                if abs(a * xs[j] + b - ys[j]) > 1.5:
                    keep[j] = False
        for t in DURATIONS_MIN:
            x0 = float(ax.x_of_t(t))
            for win in (8, 12, 20, 30, 45):
                w = (np.abs(xs - x0) <= win) & keep
                if w.sum() >= 5:
                    break
            a, b = np.polyfit(xs[w], ys[w], 1)
            y0 = a * x0 + b
            resid = np.abs(a * xs[w] + b - ys[w]).max()
            table[(T, t)] = float(ax.i_of_y(y0))
            quality[(T, t)] = {"n_points": int(w.sum()), "window_px": win,
                               "max_resid_px": float(resid)}
        quality[("total", T)] = {"accepted": int(keep.sum()), "rejected": int((~keep).sum())}
    return table, quality


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--qa-png", type=Path, default=None,
                    help="optional overlay of traced points (do not commit: it "
                         "reproduces the COP chart)")
    ap.add_argument("--allow-other-pdf", action="store_true")
    args = ap.parse_args()

    digest = sha256(args.pdf)
    if digest != EXPECTED_SHA256 and not args.allow_other_pdf:
        raise SystemExit(f"PDF SHA-256 {digest} differs from the edition this repo "
                         "was built on; re-run with --allow-other-pdf and review.")
    im = load_chart(args.pdf)
    xg, yg = detect_grid(im)
    ax = Axes(xg, yg)
    pts = trace(im, ax)
    table, quality = tabulate(pts, ax)

    # one-pixel reading uncertainty expressed as a percentage of intensity
    px_per_decade = float(abs(np.polyfit(ax.ly, ax.yg, 1)[0]))
    one_px_pct = 100 * (10 ** (1 / px_per_decade) - 1)

    out_csv = REPO / "data" / "idf_cop_appendix4_digitised.csv"
    out_csv.parent.mkdir(exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["duration_min"] + [f"T{T}_mm_per_hr" for T in RETURN_PERIODS])
        for t in DURATIONS_MIN:
            wr.writerow([t] + [f"{table[(T, t)]:.1f}" for T in RETURN_PERIODS])

    meta = {
        "source": "PUB Code of Practice on Surface Water Drainage, 7th Edition "
                  "(Dec 2018) with amendments under Addendum No. 3 (April 2025), "
                  "Appendix 4 'Rainfall Intensity-Duration-Frequency Curves for "
                  "Singapore Island', printed page 49 (PDF page 68)",
        "pdf_sha256": digest,
        "chart_pixels": list(im.shape[::-1]),
        "time_gridlines_px": [round(v, 1) for v in xg],
        "intensity_gridlines_px": [round(v, 1) for v in yg],
        "log_axis_max_deviation_px": ax.log_axis_residual_px(),
        "pixels_per_decade_intensity": round(px_per_decade, 1),
        "one_pixel_reading_uncertainty_pct": round(one_px_pct, 2),
        "points_traced": {str(T): len(pts[k]) for k, T in enumerate(RETURN_PERIODS)},
        "outliers_rejected": {str(T): quality[("total", T)]["rejected"]
                              for T in RETURN_PERIODS},
        "max_local_fit_residual_px": round(max(q["max_resid_px"] for key, q in quality.items()
                                               if key[0] != "total"), 2),
        "method": "piecewise log-axis calibration on detected grid lines; column-wise "
                  "tracking of the 8 curves (runs 2-6 px tall, grid-line bands masked); "
                  "intensity at each tabulated duration from a local linear fit of traced "
                  "points within +-8..45 px after rejecting points >1.5 px off a local line",
    }
    with open(REPO / "data" / "idf_digitisation_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    if args.qa_png:
        from PIL import Image, ImageDraw
        rgb = Image.fromarray(im.astype("uint8")).convert("RGB")
        dr = ImageDraw.Draw(rgb)
        colours = [(255, 0, 0), (0, 160, 0), (0, 0, 255), (255, 128, 0),
                   (200, 0, 200), (0, 180, 180), (128, 64, 0), (60, 60, 60)]
        for k, T in enumerate(RETURN_PERIODS):
            for x, y in pts[k]:
                dr.point((x, int(round(y))), fill=colours[k])
            for t in DURATIONS_MIN:
                x0 = float(ax.x_of_t(t))
                y0 = float(np.interp(np.log10(table[(T, t)]), ax.ly[::-1], ax.yg[::-1]))
                dr.ellipse((x0 - 3, y0 - 3, x0 + 3, y0 + 3), outline=colours[k])
        rgb.save(args.qa_png)
    print(f"wrote {out_csv.relative_to(REPO)}; 1 px = {one_px_pct:.2f}% intensity")


if __name__ == "__main__":
    main()
