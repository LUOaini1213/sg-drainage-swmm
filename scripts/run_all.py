"""Regenerate everything in results/ and README.md.

    python scripts/run_all.py            # full run (about a minute or two)
    python scripts/run_all.py --readme   # only re-render README.md from results/
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sgdrain import pipeline, readme  # noqa: E402


def main(argv: list[str]) -> None:
    if "--readme" not in argv:
        pipeline.main(write_figures=True)
    readme.write()
    print("results/ and README.md regenerated")


if __name__ == "__main__":
    main(sys.argv[1:])
