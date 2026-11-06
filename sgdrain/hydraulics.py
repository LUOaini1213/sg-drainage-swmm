"""Steady uniform open-channel flow in a rectangular (U-) drain.

Manning's formula as written in COP Clause 7.2.2 (p.30):
    Qc = (1/n) A R^(2/3) S^(1/2),  R = A / P
"""
from __future__ import annotations

import math

from .cop import G


def area(b: float, y: float) -> float:
    return b * y


def wetted_perimeter(b: float, y: float) -> float:
    # open rectangular channel: bed + two walls
    return b + 2.0 * y


def hydraulic_radius(b: float, y: float) -> float:
    return area(b, y) / wetted_perimeter(b, y)


def manning_q(b: float, y: float, s: float, n: float) -> float:
    """Discharge (m3/s) at flow depth y for width b, bed slope s, roughness n."""
    if y <= 0:
        return 0.0
    return (1.0 / n) * area(b, y) * hydraulic_radius(b, y) ** (2.0 / 3.0) * math.sqrt(s)


def manning_v(b: float, y: float, s: float, n: float) -> float:
    return manning_q(b, y, s, n) / area(b, y)


def normal_depth(q: float, b: float, s: float, n: float, y_max: float = 50.0) -> float:
    """Depth at which uniform flow carries q (bisection; Q(y) is monotonic)."""
    if q <= 0:
        return 0.0
    lo, hi = 0.0, 1.0
    while manning_q(b, hi, s, n) < q:
        hi *= 2.0
        if hi > y_max:
            raise ValueError("normal depth beyond y_max")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if manning_q(b, mid, s, n) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-10:
            break
    return 0.5 * (lo + hi)


def froude(v: float, y: float) -> float:
    """Froude number of a rectangular section (hydraulic depth = y)."""
    return v / math.sqrt(G * y)


def critical_depth(q: float, b: float) -> float:
    return (q * q / (G * b * b)) ** (1.0 / 3.0)


def capacity_with_freeboard(b: float, d: float, s: float, n: float,
                            freeboard_fraction: float) -> float:
    """Manning capacity with the water surface at (1 - freeboard) x depth."""
    return manning_q(b, (1.0 - freeboard_fraction) * d, s, n)
