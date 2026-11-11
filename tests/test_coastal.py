"""Official coastal and sea-level figures, pinned to what was read from the
sources (docs/sources.md section 6), and the datum arithmetic."""
import pytest

from sgdrain import coastal


def test_cop_platform_and_reclamation_levels():
    # COP SWD Cl. 2.1.1(a)(i), p.6 and Cl. 2.3, p.9
    assert coastal.MIN_PLATFORM_LEVEL_SHD == {"southern_coast": 4.0, "northern_coast": 4.5}
    assert coastal.MIN_RECLAMATION_LEVEL_SHD == {"southern_coast": 4.0, "northern_coast": 4.5}


def test_cpcop_planning_scenarios():
    # CPCOP 1st ed. Cl. 2.1, 2.2, 6.1
    assert coastal.CPCOP_RMSLR_PLANNING_SCENARIOS_M == (0.7, 2.15)


def test_v3_table_5_10_as_published():
    t = coastal.V3_TABLE_5_10
    assert t["Sultan Shoal"] == {
        ("SSP1-2.6", 2100): (0.51, 0.34, 0.74), ("SSP1-2.6", 2150): (0.82, 0.50, 1.24),
        ("SSP2-4.5", 2100): (0.63, 0.46, 0.88), ("SSP2-4.5", 2150): (1.05, 0.72, 1.52),
        ("SSP5-8.5", 2100): (0.85, 0.66, 1.15), ("SSP5-8.5", 2150): (1.47, 1.03, 2.12)}
    assert t["Tanjong Pagar"] == {
        ("SSP1-2.6", 2100): (0.44, 0.24, 0.69), ("SSP1-2.6", 2150): (0.71, 0.35, 1.16),
        ("SSP2-4.5", 2100): (0.56, 0.36, 0.82), ("SSP2-4.5", 2150): (0.94, 0.56, 1.43),
        ("SSP5-8.5", 2100): (0.78, 0.56, 1.10), ("SSP5-8.5", 2150): (1.36, 0.89, 2.02)}
    assert coastal.V3_SINGAPORE_AVERAGE[("SSP5-8.5", 2100)] == (0.79, 0.04)
    assert coastal.V3_SINGAPORE_AVERAGE[("SSP5-8.5", 2150)] == (1.37, 0.06)
    assert coastal.V3_BASELINE == "1995-2014"
    for gauge in t.values():
        for (scen, year), (med, lo, hi) in gauge.items():
            assert lo <= med <= hi
            later = gauge[(scen, 2150)]
            assert later[0] >= gauge[(scen, 2100)][0]       # rise grows with time
    # the headline "up to 1.15m by 2100" is the top of the Sultan Shoal SSP5-8.5 range
    tops_2100 = [d[k][2] for d in t.values() for k in d if k[1] == 2100]
    assert max(tops_2100) == 1.15


def test_slr_scenarios_are_the_cited_figures():
    s = coastal.SLR_SCENARIOS
    assert [x["id"] for x in s] == ["present", "cpcop_0p7", "v3_ssp585_2100_high", "cpcop_2p15"]
    assert [x["rise_m"] for x in s] == [0.0, 0.7, 1.15, 2.15]
    assert s[2]["rise_m"] == coastal.V3_TABLE_5_10["Sultan Shoal"][("SSP5-8.5", 2100)][2]
    assert {s[1]["rise_m"], s[3]["rise_m"]} == set(coastal.CPCOP_RMSLR_PLANNING_SCENARIOS_M)
    for x in s[1:]:
        assert f"{x['rise_m']}" in x["label"]      # the label states the figure used


def test_datum_assumption_is_anchored_on_the_cop():
    assert coastal.OUTFALL_GROUND_SHD_BASE == coastal.MIN_PLATFORM_LEVEL_SHD["southern_coast"]
    assert coastal.OUTFALL_GROUND_SHD_BASE in coastal.OUTFALL_GROUND_SHD_SENSITIVITY
    assert coastal.MIN_PLATFORM_LEVEL_SHD["northern_coast"] in coastal.OUTFALL_GROUND_SHD_SENSITIVITY
    assert coastal.TIDE_MEAN_SHD == 0.0


def test_local_shd_conversion():
    g = 8.6
    assert coastal.local_to_shd(8.6, g) == pytest.approx(4.0)
    assert coastal.local_to_shd(7.4, g) == pytest.approx(2.8)
    assert coastal.local_to_shd(8.6, g, 3.0) == pytest.approx(3.0)
    assert coastal.local_to_shd(9.0, g, 2.5) == pytest.approx(2.9)
    for z in (5.0, 7.4, 8.6, 10.2):
        for gs in (2.5, 4.0, 4.5):
            assert coastal.shd_to_local(coastal.local_to_shd(z, g, gs), g, gs) == pytest.approx(z)
            # moving the assumed outfall ground moves every level by the same amount
            assert (coastal.local_to_shd(z, g, gs) - coastal.local_to_shd(z, g, 4.0)
                    == pytest.approx(gs - 4.0))


def test_chart_datum_conversion():
    assert coastal.cd_to_shd(3.4, 1.9418) == pytest.approx(1.4582)
    assert coastal.cd_to_shd(1.9418, 1.9418) == pytest.approx(0.0)
    assert coastal.cd_to_shd(1.9418, 1.9418, 0.25) == pytest.approx(0.25)
    assert coastal.cd_to_shd(0.1, 1.9418) == pytest.approx(-1.8418)


def test_cop_pump_formula():
    # COP Cl. 10.1(a): P = I A / (3.6 x 10^6); 1 mm/hr over 3.6 km2 = 1 m3/s
    assert coastal.cop_pump_capacity_m3s(3.6e6, 1.0) == pytest.approx(1.0)
    assert coastal.cop_pump_capacity_m3s(126_000) == pytest.approx(5.25)
    assert coastal.PUMP_DESIGN_INTENSITY_MM_HR == 150.0
