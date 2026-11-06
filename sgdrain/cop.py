"""Design criteria taken from PUB's Code of Practice on Surface Water Drainage.

Edition used: Seventh Edition (Dec 2018) with amendments under Addendum No. 3
(April 2025), downloaded from pub.gov.sg on 2026-11-06 (see docs/sources.md).
Page references are the printed page number followed by the PDF page number.

Only values that were read from that document are defined here.  Anything the
COP does not specify (e.g. the overland-flow time inside its 5-15 min range,
the drain size catalogue, SWMM loss parameters) is an assumption and lives in
``data/catchment.json`` or ``sgdrain/swmm_model.py`` with its own source.
"""
from __future__ import annotations

import math

COP_EDITION = ("PUB Code of Practice on Surface Water Drainage, Seventh Edition "
               "(Dec 2018) with amendments under Addendum No. 3 (April 2025)")

# Clause 7.1.1, p.27 (PDF p.46): Qr = (1/360) C I A, Qr in m3/s, I in mm/hr, A in ha.
RATIONAL_DIVISOR = 360.0

# Clause 7.1.2, p.27 (PDF p.46) - table as replaced by Addendum No. 3, S/No. 17
# (PDF p.8).  "For developments with composite surface characteristics, a
# weighted value of C may be adopted."
RUNOFF_C = {
    "road": 1.00,       # Roads, highways, airport runways, paved up areas
    "urban": 0.90,      # Urban areas
    "vegetated": 0.45,  # Vegetated and pervious areas
}

# Clause 7.1.3, p.28 (PDF p.47): design return period by catchment area served:
# "less than 100 ha" 10 yr; "100 to 1000 ha" 25 yr; "more than 1000 ha" 50 yr.
RETURN_PERIOD_BY_AREA = [(100.0, 10), (1000.0, 25), (math.inf, 50)]
RETURN_PERIOD_SPECIAL = 100  # airport runway or any area specified by the Board

# Clause 7.1.4, p.28 (PDF p.47): tc = to + td; overland flow time to 5-15 min.
OVERLAND_TIME_MIN = 5.0
OVERLAND_TIME_MAX = 15.0

# Clause 7.2.3, p.30 (PDF p.49): Manning roughness coefficients.
MANNING_N = {
    "upvc": 0.0125,
    "concrete": 0.0150,
    "brick": 0.0170,
    "earth": 0.0270,
    "earth_stones_weed": 0.0350,
    "gravel": 0.0300,
}

# Clause 7.3.1, p.31 (PDF p.50): velocity not lower than 1.0 m/s (self-cleansing).
V_MIN = 1.0
# Clause 7.3.2, p.31 (PDF p.50): concrete-lined drain max 3.0 m/s or below the
# critical velocity, whichever is lower.
V_MAX_CONCRETE = 3.0
# Clause 7.3.3, p.31 (PDF p.50): sub-critical flow, Froude number within the
# range from 0.8 decreasing (i.e. Fr <= 0.8).
FROUDE_MAX = 0.8
# Clause 7.3.4, p.31 (PDF p.50): freeboard generally 15% of drain depth.
FREEBOARD_FRACTION = 0.15

# Clause 4.3.1, p.12 (PDF p.31): "The internal width and clear depth of a
# roadside drain (including entrance culvert) shall be at least 600 mm."  The
# clause sits under 4.3 "Closed Drainage System"; this screening applies the
# same minimum to every drain (assumption, see README).
MIN_DRAIN_DIMENSION_M = 0.6

G = 9.81  # m/s2


def rational_q(c: float, i_mm_hr: float, area_ha: float) -> float:
    """Peak runoff (m3/s) by the Rational Formula, Clause 7.1.1."""
    return c * i_mm_hr * area_ha / RATIONAL_DIVISOR


def design_return_period(total_area_ha: float) -> int:
    """Return period (years) for the area served, Clause 7.1.3."""
    if total_area_ha <= 0:
        raise ValueError(total_area_ha)
    if total_area_ha < RETURN_PERIOD_BY_AREA[0][0]:
        return RETURN_PERIOD_BY_AREA[0][1]
    if total_area_ha <= RETURN_PERIOD_BY_AREA[1][0]:
        return RETURN_PERIOD_BY_AREA[1][1]
    return RETURN_PERIOD_BY_AREA[2][1]


def weighted_c(fractions: dict[str, float]) -> float:
    """Area-weighted runoff coefficient (Clause 7.1.2 note)."""
    total = sum(fractions.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"land-use fractions sum to {total}, not 1")
    return sum(RUNOFF_C[k] * f for k, f in fractions.items())


def as_dict() -> dict:
    """All COP values used, for results/inputs_used.json."""
    return {
        "edition": COP_EDITION,
        "rational_divisor": RATIONAL_DIVISOR,
        "runoff_c": RUNOFF_C,
        "return_period_by_area": [[None if math.isinf(u) else u, y]
                                  for u, y in RETURN_PERIOD_BY_AREA],
        "overland_time_min_range": [OVERLAND_TIME_MIN, OVERLAND_TIME_MAX],
        "manning_n_concrete": MANNING_N["concrete"],
        "v_min": V_MIN,
        "v_max_concrete": V_MAX_CONCRETE,
        "froude_max": FROUDE_MAX,
        "freeboard_fraction": FREEBOARD_FRACTION,
        "freeboard_pct": round(100 * FREEBOARD_FRACTION),
        "min_drain_dimension_m": MIN_DRAIN_DIMENSION_M,
        "min_drain_dimension_mm": round(1000 * MIN_DRAIN_DIMENSION_M),
    }
