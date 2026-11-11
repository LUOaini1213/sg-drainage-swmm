"""Tide boundary for the outfall, built from published tide predictions.

Data: MPA tide predictions for November-December 2026 as published on NEA's
"Tide Timings" page: times and heights of high (H) and low (L) water, metres
above Chart Datum, 0.1 m resolution.  The page does not name the station and
does not state the time zone (Singapore time is assumed).

The full table is NOT in this repository: NEA's website terms do not allow
its contents to be redistributed.  What is committed is a small extract,
data/tide_extract_mpa_2026-11_12.json: summary statistics computed from the
table, and the three predicted extremes around the highest high water, which
are all the runs need.  scripts/make_tide_extract.py rebuilds the extract from
a local copy of the table (data/local/, git-ignored); docs/sources.md section
6.4 says how to obtain one.

Between successive high and low waters the level follows a half cosine, the
usual way to read a curve from tide-table extremes.  That interpolation is an
assumption of this project, not part of the published data.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
EXTRACT = _DATA_DIR / "tide_extract_mpa_2026-11_12.json"
LOCAL_TABLE = _DATA_DIR / "local" / "tide_predictions_mpa_2026-11_12.csv"   # not redistributed
HEIGHT_RESOLUTION_M = 0.1   # heights are published to one decimal


@dataclass(frozen=True)
class Extreme:
    time: datetime
    height_cd: float
    kind: str  # "H" or "L"


@dataclass(frozen=True)
class Extract:
    events: list[Extreme]      # the extremes that bracket the simulated window
    stats: dict                # statistics of the full table (see stats())
    mean_level_cd: float       # time-mean of the full table's curve, unrounded
    table_sha256: str          # SHA-256 of the full table the extract was built from


def check_sequence(ev: list[Extreme]) -> None:
    for a, b in zip(ev, ev[1:]):
        if a.kind == b.kind:
            raise ValueError(f"two consecutive {a.kind} waters at {a.time} and {b.time}")
        if (a.kind == "H" and a.height_cd < b.height_cd) or (a.kind == "L" and a.height_cd > b.height_cd):
            raise ValueError(f"high water below the adjacent low water at {a.time}")


def load(path: Path = LOCAL_TABLE) -> list[Extreme]:
    """Read a full table of predicted extremes (date,time,height_m_cd,type)."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    ev = [Extreme(datetime.fromisoformat(f"{r['date']}T{r['time']}"), float(r["height_m_cd"]),
                  r["type"]) for r in rows]
    ev.sort(key=lambda e: e.time)
    check_sequence(ev)
    return ev


def level_at(ev: list[Extreme], t: datetime) -> float:
    """Tide height (m above CD) at time t, half-cosine between extremes."""
    for a, b in zip(ev, ev[1:]):
        if a.time <= t <= b.time:
            f = (t - a.time).total_seconds() / (b.time - a.time).total_seconds()
            return a.height_cd + (b.height_cd - a.height_cd) * (1.0 - math.cos(math.pi * f)) / 2.0
    raise ValueError(f"{t} is outside the predictions ({ev[0].time} to {ev[-1].time})")


def mean_level(ev: list[Extreme]) -> float:
    """Time-mean of the interpolated curve over the whole prediction window.

    The mean of a half cosine between two extremes is their average, so the
    integral is exact: sum((h_a + h_b) / 2 * dt) / sum(dt)."""
    num = den = 0.0
    for a, b in zip(ev, ev[1:]):
        dt = (b.time - a.time).total_seconds()
        num += 0.5 * (a.height_cd + b.height_cd) * dt
        den += dt
    return num / den


def highest_high_water(ev: list[Extreme]) -> Extreme:
    """The highest predicted high water (earliest one if tied)."""
    top = max(e.height_cd for e in ev if e.kind == "H")
    return next(e for e in ev if e.kind == "H" and e.height_cd == top)


def stats(ev: list[Extreme]) -> dict:
    hw = [e.height_cd for e in ev if e.kind == "H"]
    lw = [e.height_cd for e in ev if e.kind == "L"]
    top = highest_high_water(ev)
    return {
        "n_extremes": len(ev), "n_high": len(hw), "n_low": len(lw),
        "first": ev[0].time.isoformat(timespec="minutes"),
        "last": ev[-1].time.isoformat(timespec="minutes"),
        "highest_hw_cd": top.height_cd,
        "highest_hw_time": top.time.isoformat(timespec="minutes"),
        "n_highest_hw": sum(1 for h in hw if h == top.height_cd),
        "mean_hw_cd": round(sum(hw) / len(hw), 4),
        "mean_lw_cd": round(sum(lw) / len(lw), 4),
        "lowest_lw_cd": min(lw),
        "mean_level_cd": round(mean_level(ev), 4),
    }


def aligned_curve(ev: list[Extreme], hw: Extreme, peak_offset_min: float, duration_min: int,
                  step_min: int) -> list[tuple[float, float]]:
    """(minutes from simulation start, height above CD), with high water ``hw``
    placed ``peak_offset_min`` after the start."""
    t0 = hw.time - timedelta(minutes=peak_offset_min)
    n = int(round(duration_min / step_min))
    return [(k * step_min, level_at(ev, t0 + timedelta(minutes=k * step_min))) for k in range(n + 1)]


# ------------------------------------------------------------------ extract
def bracketing(ev: list[Extreme], start: datetime, end: datetime) -> list[Extreme]:
    """The consecutive extremes from the last one at or before ``start`` to the
    first one at or after ``end``: the fewest that define the curve on [start, end]."""
    before = [i for i, e in enumerate(ev) if e.time <= start]
    after = [i for i, e in enumerate(ev) if e.time >= end]
    if not before or not after:
        raise ValueError(f"[{start}, {end}] is outside the predictions ({ev[0].time} to {ev[-1].time})")
    return ev[before[-1]:after[0] + 1]


def build_extract(ev: list[Extreme], peak_offset_min: float, duration_min: int) -> dict:
    """What the runs need from a full table: its statistics, its unrounded mean
    level, and the extremes around the highest high water that bracket a run of
    ``duration_min`` with high water ``peak_offset_min`` after the start."""
    hw = highest_high_water(ev)
    start = hw.time - timedelta(minutes=peak_offset_min)
    win = bracketing(ev, start, start + timedelta(minutes=duration_min))
    return {
        "stats": stats(ev),
        "mean_level_cd": mean_level(ev),
        "window": [{"date": e.time.strftime("%Y-%m-%d"), "time": e.time.strftime("%H:%M"),
                    "height_m_cd": e.height_cd, "type": e.kind} for e in win],
    }


def load_extract(path: Path = EXTRACT) -> Extract:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    ev = [Extreme(datetime.fromisoformat(f"{r['date']}T{r['time']}"), float(r["height_m_cd"]),
                  r["type"]) for r in d["window"]]
    check_sequence(ev)
    st = d["stats"]
    top = highest_high_water(ev)
    if (top.height_cd, top.time.isoformat(timespec="minutes")) != (st["highest_hw_cd"], st["highest_hw_time"]):
        raise ValueError("the extract's window is not the one around the table's highest high water")
    if round(d["mean_level_cd"], 4) != st["mean_level_cd"]:
        raise ValueError("the extract's mean level disagrees with its statistics")
    return Extract(ev, st, float(d["mean_level_cd"]), d["table_sha256"])
