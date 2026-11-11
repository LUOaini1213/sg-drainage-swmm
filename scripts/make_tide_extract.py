"""Rebuild data/tide_extract_mpa_2026-11_12.json from a local copy of the full tide table.

    python scripts/make_tide_extract.py

The full table of predicted high and low waters is not in the repository (NEA's
website terms do not allow redistribution).  To rebuild the extract, copy the
November and December 2026 tables from https://www.nea.gov.sg/weather/tide-timings
into data/local/tide_predictions_mpa_2026-11_12.csv with the header
``date,time,height_m_cd,type`` (ISO date, HH:MM, metres above Chart Datum, H or L).
The extract keeps only summary statistics and the extremes that bracket the
simulated window around the highest high water.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sgdrain import network, tide, tide_pipeline  # noqa: E402

SOURCE = ("MPA tide predictions (high and low waters, metres above Chart Datum) as published on "
          "NEA's Tide Timings page, https://www.nea.gov.sg/weather/tide-timings, "
          "November and December 2026 tables, retrieved 2026-11-09")
NOTE = ("Extract only. The full table is not redistributed here. 'stats' and 'mean_level_cd' are "
        "computed from the full table; 'window' holds the predicted extremes that bracket the "
        "simulated window around the highest predicted high water.")


def extract_from(table: Path) -> dict:
    ev = tide.load(table)
    body = tide.build_extract(ev, tide_pipeline.design_peak_minute(network.load()),
                              tide_pipeline.SIM_MIN)
    return {"source": SOURCE, "note": NOTE,
            "table_sha256": hashlib.sha256(table.read_bytes()).hexdigest(), **body}


def main() -> None:
    if not tide.LOCAL_TABLE.exists():
        sys.exit("no local table at data/local/tide_predictions_mpa_2026-11_12.csv: "
                 "see the docstring of this script")
    d = extract_from(tide.LOCAL_TABLE)
    tide.EXTRACT.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {tide.EXTRACT.name}: {len(d['window'])} extremes, mean level {d['mean_level_cd']:.4f} m CD")


if __name__ == "__main__":
    main()
