"""The COP values are the specification: these tests pin them to what was read
from the Seventh Edition (Dec 2018) with Addendum No. 3 (April 2025)."""
import pytest

from sgdrain import cop


def test_cop_constants_match_the_code():
    assert cop.RATIONAL_DIVISOR == 360.0                       # Cl. 7.1.1
    assert cop.RUNOFF_C == {"road": 1.00, "urban": 0.90, "vegetated": 0.45}  # Cl. 7.1.2
    assert (cop.OVERLAND_TIME_MIN, cop.OVERLAND_TIME_MAX) == (5.0, 15.0)     # Cl. 7.1.4
    assert cop.MANNING_N["concrete"] == 0.0150                  # Cl. 7.2.3
    assert cop.MANNING_N["upvc"] == 0.0125
    assert cop.V_MIN == 1.0                                     # Cl. 7.3.1
    assert cop.V_MAX_CONCRETE == 3.0                            # Cl. 7.3.2
    assert cop.FROUDE_MAX == 0.8                                # Cl. 7.3.3
    assert cop.FREEBOARD_FRACTION == 0.15                       # Cl. 7.3.4
    assert cop.MIN_DRAIN_DIMENSION_M == 0.6                     # Cl. 4.3.1


def test_rational_formula_arithmetic():
    assert cop.rational_q(1.0, 360.0, 1.0) == pytest.approx(1.0)
    assert cop.rational_q(0.5, 100.0, 2.0) == pytest.approx(100.0 / 360.0)
    assert cop.rational_q(0.9, 180.0, 4.0) == pytest.approx(1.8)


def test_return_period_rule():
    assert cop.design_return_period(12.6) == 10
    assert cop.design_return_period(99.99) == 10
    assert cop.design_return_period(100.0) == 25       # "100 to 1000 ha"
    assert cop.design_return_period(1000.0) == 25
    assert cop.design_return_period(1000.01) == 50     # "more than 1000 ha"
    with pytest.raises(ValueError):
        cop.design_return_period(0)


def test_weighted_c():
    assert cop.weighted_c({"road": 0.2, "urban": 0.65, "vegetated": 0.15}) == pytest.approx(0.8525)
    assert cop.weighted_c({"road": 1.0, "urban": 0.0, "vegetated": 0.0}) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        cop.weighted_c({"road": 0.5, "urban": 0.4, "vegetated": 0.0})
