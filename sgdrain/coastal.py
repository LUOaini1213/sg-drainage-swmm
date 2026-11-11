"""Official Singapore coastal and sea-level figures used by the tide / sea-level
stress test, plus the datum assumption that ties the SYNTHETIC catchment to them.

Every number here was read from the source named next to it (retrieved
2026-11-09; full references, URLs and page numbers in docs/sources.md).  Page
references are printed page / PDF page.  Nothing is interpolated: where a
source gives no horizon year, none is attached.

Values marked ASSUMPTION are this project's choices, not official figures.
"""
from __future__ import annotations

# ---------------------------------------------------------------- PUB COP SWD
# Code of Practice on Surface Water Drainage, 7th ed. (Dec 2018) with
# Addendum No. 3 (Apr 2025).
# Cl. 2.1.1(a)(i), p.6 / PDF p.25: minimum platform level "4.0m above Singapore
# Height Datum for developments along the southern coast; and 4.5m above
# Singapore Height Datum for developments along the northern coast".
# Cl. 2.3, p.9 / PDF p.28: the minimum reclamation level uses the same values.
MIN_PLATFORM_LEVEL_SHD = {"southern_coast": 4.0, "northern_coast": 4.5}
MIN_RECLAMATION_LEVEL_SHD = {"southern_coast": 4.0, "northern_coast": 4.5}

# Cl. 10.1(a), p.38 / PDF p.57 (pumped drainage for underground facilities,
# referred to from Cl. 4.9): pumping capacity P = I A / (3.6 x 10^6) with I not
# less than 150 mm/hr over the entire source catchment.  Used here only to
# give a sense of scale for the pump estimate; the clause does not govern
# estate outfalls.
PUMP_DESIGN_INTENSITY_MM_HR = 150.0
PUMP_FORMULA_DIVISOR = 3.6e6


def cop_pump_capacity_m3s(area_m2: float, intensity_mm_hr: float = PUMP_DESIGN_INTENSITY_MM_HR) -> float:
    """COP Cl. 10.1(a): P = I A / (3.6 x 10^6), P in m3/s, I in mm/hr, A in m2."""
    return intensity_mm_hr * area_m2 / PUMP_FORMULA_DIVISOR


# ------------------------------------------------------------- PUB CPCOP
# Code of Practice on Coastal Protection, First Edition (June 2026).
# Cl. 2.1, 2.2 (p.12 / PDF p.13) and Cl. 6.1 (p.18 / PDF p.19): the "0.7m RMSLR
# planning scenario" and the "2.15m RMSLR planning scenario".  The code does
# not attach a year to either scenario.
CPCOP_RMSLR_PLANNING_SCENARIOS_M = (0.7, 2.15)

# ------------------------------------------------------------- MSS V3
# Third National Climate Change Study (V3), Report for Stakeholders,
# Chapter 5, Table 5.10 (p.63 / chapter PDF p.15): projected relative sea-level
# rise by 2100 and 2150, median (likely range), medium confidence, relative to
# the IPCC AR6 baseline 1995-2014 (Section 5.14.2, p.62).
V3_TABLE_5_10 = {
    # gauge: {(scenario, year): (median, likely_low, likely_high)}
    "Sultan Shoal": {
        ("SSP1-2.6", 2100): (0.51, 0.34, 0.74), ("SSP1-2.6", 2150): (0.82, 0.50, 1.24),
        ("SSP2-4.5", 2100): (0.63, 0.46, 0.88), ("SSP2-4.5", 2150): (1.05, 0.72, 1.52),
        ("SSP5-8.5", 2100): (0.85, 0.66, 1.15), ("SSP5-8.5", 2150): (1.47, 1.03, 2.12),
    },
    "Tanjong Pagar": {
        ("SSP1-2.6", 2100): (0.44, 0.24, 0.69), ("SSP1-2.6", 2150): (0.71, 0.35, 1.16),
        ("SSP2-4.5", 2100): (0.56, 0.36, 0.82), ("SSP2-4.5", 2150): (0.94, 0.56, 1.43),
        ("SSP5-8.5", 2100): (0.78, 0.56, 1.10), ("SSP5-8.5", 2150): (1.36, 0.89, 2.02),
    },
}
# "Singapore Average" row of Table 5.10 (average of the six gauge medians,
# +/- one standard error across gauges).
V3_SINGAPORE_AVERAGE = {
    ("SSP1-2.6", 2100): (0.45, 0.03), ("SSP1-2.6", 2150): (0.72, 0.05),
    ("SSP2-4.5", 2100): (0.57, 0.04), ("SSP2-4.5", 2150): (0.95, 0.06),
    ("SSP5-8.5", 2100): (0.79, 0.04), ("SSP5-8.5", 2150): (1.37, 0.06),
}
V3_BASELINE = "1995-2014"

# Sea-level rise scenarios run against the tide.  Each is one official figure,
# copied as published (no interpolation between years or scenarios).
SLR_SCENARIOS = [
    {"id": "present", "rise_m": 0.0, "label": "today's tide (2026 predictions)",
     "source": "no rise added"},
    {"id": "cpcop_0p7", "rise_m": CPCOP_RMSLR_PLANNING_SCENARIOS_M[0],
     "label": "+0.7 m (CPCOP 0.7m RMSLR planning scenario)",
     "source": "PUB CPCOP 1st ed. (June 2026) Cl. 2.1, 2.2, 6.1; no year attached"},
    {"id": "v3_ssp585_2100_high", "rise_m": V3_TABLE_5_10["Sultan Shoal"][("SSP5-8.5", 2100)][2],
     "label": "+1.15 m (V3 SSP5-8.5, 2100, top of likely range)",
     "source": "MSS V3 Report for Stakeholders, Table 5.10, Sultan Shoal, SSP5-8.5, 2100, 83rd percentile"},
    {"id": "cpcop_2p15", "rise_m": CPCOP_RMSLR_PLANNING_SCENARIOS_M[1],
     "label": "+2.15 m (CPCOP 2.15m RMSLR planning scenario)",
     "source": "PUB CPCOP 1st ed. (June 2026) Cl. 2.1, 6.1; no year attached"},
]

# MSE, 2nd Reading of the Coastal Protection Bill, opening speech, 6 March 2026:
# sea levels "reaching up to 5 metres above today's mean sea level when coupled
# with storm surges and high tides".  Quoted for context: no surge is modelled.
COMBINED_EXTREME_ABOVE_MSL_M = 5.0

# ------------------------------------------------------------ ASSUMPTIONS
# The catchment levels are on an arbitrary local datum.  ASSUMPTION A1: the
# ground at the outfall node sits exactly at the COP minimum platform level for
# the southern coast.  The sensitivity runs move it between these levels.
OUTFALL_GROUND_SHD_BASE = MIN_PLATFORM_LEVEL_SHD["southern_coast"]
OUTFALL_GROUND_SHD_SENSITIVITY = (4.5, 4.0, 3.5, 3.0, 2.5)
# ASSUMPTION A2: the time-mean of the published tide predictions (metres above
# Chart Datum) is taken as 0.0 m SHD.  SHD is the 1935-37 mean sea level at
# Victoria Dock (NCCS); the official CD-to-SHD conversion is only available
# from MPA's Hydrographic Division (CPCOP terminology) and was not obtained.
TIDE_MEAN_SHD = 0.0


def local_to_shd(z_local: float, outfall_ground_local: float,
                 outfall_ground_shd: float = OUTFALL_GROUND_SHD_BASE) -> float:
    """Convert a level on the catchment's local datum to SHD (ASSUMPTION A1)."""
    return z_local - outfall_ground_local + outfall_ground_shd


def shd_to_local(z_shd: float, outfall_ground_local: float,
                 outfall_ground_shd: float = OUTFALL_GROUND_SHD_BASE) -> float:
    return z_shd - outfall_ground_shd + outfall_ground_local


def cd_to_shd(h_cd: float, tide_mean_cd: float, tide_mean_shd: float = TIDE_MEAN_SHD) -> float:
    """Tide height above Chart Datum -> SHD (ASSUMPTION A2)."""
    return h_cd - tide_mean_cd + tide_mean_shd


def as_dict() -> dict:
    return {
        "min_platform_level_shd": MIN_PLATFORM_LEVEL_SHD,
        "min_reclamation_level_shd": MIN_RECLAMATION_LEVEL_SHD,
        "cpcop_rmslr_planning_scenarios_m": list(CPCOP_RMSLR_PLANNING_SCENARIOS_M),
        "v3_baseline": V3_BASELINE,
        "v3_table_5_10": {g: {f"{k[0]} {k[1]}": list(v) for k, v in d.items()}
                          for g, d in V3_TABLE_5_10.items()},
        "v3_singapore_average": {f"{k[0]} {k[1]}": list(v) for k, v in V3_SINGAPORE_AVERAGE.items()},
        # dot-free keys for the README
        "v3_ssp585_2100_singapore_average_m": V3_SINGAPORE_AVERAGE[("SSP5-8.5", 2100)][0],
        "v3_ssp585_2150_sultan_shoal_likely_high_m": V3_TABLE_5_10["Sultan Shoal"][("SSP5-8.5", 2150)][2],
        "slr_scenarios": SLR_SCENARIOS,
        "combined_extreme_above_msl_m": COMBINED_EXTREME_ABOVE_MSL_M,
        "outfall_ground_shd_base": OUTFALL_GROUND_SHD_BASE,
        "outfall_ground_shd_sensitivity": list(OUTFALL_GROUND_SHD_SENSITIVITY),
        "tide_mean_shd": TIDE_MEAN_SHD,
        "pump_design_intensity_mm_hr": PUMP_DESIGN_INTENSITY_MM_HR,
    }
