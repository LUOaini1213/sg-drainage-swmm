"""Rainfall intensity from the digitised COP Appendix 4 IDF curves.

The COP (Clause 7.1.3, p.28) refers to the IDF curves for Singapore Island in
Appendix 4 (p.49), which are published only as a chart.  The values used here
were digitised from that chart by ``tools/digitize_idf.py``; see
``data/idf_digitisation_meta.json`` for the calibration and reading
uncertainty.  Between tabulated durations the curves are interpolated linearly
in log(duration)-log(intensity) space, i.e. on the chart's own axes.
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "idf_cop_appendix4_digitised.csv"


@lru_cache(maxsize=None)
def load_table(path: str = str(DATA)) -> tuple[tuple[float, ...], dict[int, tuple[float, ...]]]:
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    periods = [int(h.split("_")[0][1:]) for h in header[1:]]
    durations = tuple(float(r[0]) for r in body)
    table = {T: tuple(float(r[j + 1]) for r in body) for j, T in enumerate(periods)}
    return durations, table


def intensity(return_period: int, duration_min: float, uplift: float = 0.0) -> float:
    """Average intensity (mm/hr) for a storm of the given duration.

    ``uplift`` is a fractional climate-change increase applied
    multiplicatively (0.10 = +10 %).
    """
    durations, table = load_table()
    if return_period not in table:
        raise KeyError(f"no digitised curve for T={return_period}")
    if not durations[0] - 1e-9 <= duration_min <= durations[-1] + 1e-9:
        raise ValueError(f"duration {duration_min} min outside digitised range "
                         f"{durations[0]}-{durations[-1]} min")
    vals = table[return_period]
    lx = [math.log(d) for d in durations]
    x = math.log(duration_min)
    for j in range(len(lx) - 1):
        if lx[j] <= x <= lx[j + 1]:
            w = (x - lx[j]) / (lx[j + 1] - lx[j])
            li = (1 - w) * math.log(vals[j]) + w * math.log(vals[j + 1])
            return math.exp(li) * (1.0 + uplift)
    return vals[-1] * (1.0 + uplift)


def depth_mm(return_period: int, duration_min: float, uplift: float = 0.0) -> float:
    return intensity(return_period, duration_min, uplift) * duration_min / 60.0
