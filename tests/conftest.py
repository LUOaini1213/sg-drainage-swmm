import csv
import json
from pathlib import Path

import pytest

from sgdrain import cop, network, rational

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"


def read_csv(name):
    with open(RESULTS / name, newline="") as f:
        return list(csv.DictReader(f))


def read_json(name):
    return json.loads((RESULTS / name).read_text())


@pytest.fixture(scope="session")
def net():
    return network.load()


@pytest.fixture(scope="session")
def T(net):
    return cop.design_return_period(net.total_area_ha)


@pytest.fixture(scope="session")
def design(net, T):
    return rational.run(net, T)


@pytest.fixture(scope="session")
def secs(design):
    return rational.sections(design)


@pytest.fixture(scope="session")
def swmm_design(net, secs, T, tmp_path_factory):
    """Fresh SWMM run of the design network for the design storm."""
    from sgdrain import hyetograph, swmm_model, pipeline
    inv = rational.inverts(net, secs)
    hy = hyetograph.alternating_block(T, pipeline.STORM_DURATION_MIN, pipeline.STORM_DT_MIN)
    text = swmm_model.build_inp(net, secs, inv, hy, pipeline.STORM_DT_MIN, "test")
    p = tmp_path_factory.mktemp("swmm") / "design.inp"
    p.write_text(text)
    return swmm_model.run_inp(p), text
