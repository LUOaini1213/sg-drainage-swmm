"""Design hyetograph by the alternating block method.

Method (Chow, Maidment & Mays, 1988, Applied Hydrology, Ch. 14 "Design
Storms"): for block length dt and n blocks, take the IDF depth P(k dt) for
k = 1..n, form the increments dP_k = P(k dt) - P((k-1) dt), and place the
largest increment in the central block, then the remaining increments in
descending order alternately to the right and left of it.  The central
window of k blocks then holds the k largest increments, i.e. at least the IDF
depth for duration k dt (exactly, where the depth-duration curve is concave),
so the storm contains the design intensity for every duration up to its
length.

The COP does not prescribe a hyetograph; this choice is ours (see README).
"""
from __future__ import annotations

from . import idf


def alternating_block(return_period: int, duration_min: int = 120, dt_min: int = 5,
                      uplift: float = 0.0) -> list[float]:
    """Block intensities (mm/hr), in time order."""
    if duration_min % dt_min:
        raise ValueError("duration must be a multiple of dt")
    n = duration_min // dt_min
    cum = [idf.depth_mm(return_period, k * dt_min, uplift) for k in range(1, n + 1)]
    inc = [cum[0]] + [cum[k] - cum[k - 1] for k in range(1, n)]
    if min(inc) < 0:
        raise ValueError("IDF depth not monotonic in duration")
    order = sorted(inc, reverse=True)
    blocks = [0.0] * n
    centre = (n - 1) // 2
    blocks[centre] = order[0]
    left, right = centre - 1, centre + 1
    for j, v in enumerate(order[1:]):
        if j % 2 == 0 and right < n:      # second largest to the right
            blocks[right] = v
            right += 1
        elif left >= 0:
            blocks[left] = v
            left -= 1
        else:
            blocks[right] = v
            right += 1
    return [d * 60.0 / dt_min for d in blocks]
