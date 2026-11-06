import pytest

from sgdrain import pipeline, rational
from conftest import read_csv, read_json


@pytest.fixture(scope="module")
def stress():
    return read_json("stress_summary.json")


@pytest.mark.parametrize("key", list(pipeline.STRESS_SCENARIOS))
def test_rational_failures_reproduce(net, secs, stress, key):
    sc = pipeline.STRESS_SCENARIOS[key]
    chk = rational.run(net, sc["T"], sc["uplift"], mode="check", fixed=secs)
    fails = pipeline.failing_reaches(chk)
    assert sorted(fails) == stress["scenarios"][key]["rational_failing_reaches"]
    for r in chk:
        assert (r.reach in fails) == (not (r.freeboard_ok and r.vmax_ok and r.froude_ok))


@pytest.mark.parametrize("key", list(pipeline.STRESS_SCENARIOS))
def test_upsizing_never_shrinks_and_restores_compliance(net, secs, stress, key):
    sc = pipeline.STRESS_SCENARIOS[key]
    up = rational.run(net, sc["T"], sc["uplift"], mode="upsize", fixed=secs)
    up_secs = rational.sections(up)
    for r in up:
        b0, d0, s0 = secs[r.reach]
        assert r.width_m >= b0 - 1e-9 and r.depth_m >= d0 - 1e-9
        assert r.slope == s0
        assert r.compliant
    # independent check of the upsized network under the stressed storm
    chk = rational.run(net, sc["T"], sc["uplift"], mode="check", fixed=up_secs)
    assert all(r.compliant for r in chk)
    # minimal: no smaller catalogue section (not shrinking) passes at that flow
    for r in up:
        b0, d0, _ = secs[r.reach]
        for b, d in rational.CATALOGUE:
            if b >= b0 - 1e-9 and d >= d0 - 1e-9 and b * d < r.width_m * r.depth_m - 1e-9:
                assert not rational.check_section(r.q_m3s, b, d, r.slope).ok
    changed = {r.reach for r in up if (r.width_m, r.depth_m) != secs[r.reach][:2]}
    assert changed == set(stress["scenarios"][key]["upsized_reaches"])


def test_every_failing_reach_is_upsized(stress):
    for key, sc in stress["scenarios"].items():
        assert set(sc["upsized_reaches"]) >= set(sc["rational_failing_reaches"])
        assert sc["upsized_all_compliant"]


def test_uplift_sweep_monotonic_and_first_failure(net, secs, T, stress):
    rows = read_csv("uplift_sweep_rational.csv")
    ups = [int(r["uplift_pct"]) for r in rows]
    assert ups == list(range(0, 93))
    nfail = [int(r["n_failing"]) for r in rows]
    assert nfail[0] == 0
    assert all(b >= a for a, b in zip(nfail, nfail[1:]))
    for rid in [r.id for r in net.reaches]:
        u = [float(r[f"util_{rid}"]) for r in rows]
        assert all(b > a for a, b in zip(u, u[1:]))
    # first-failure uplift: passes 1 % below, fails at it
    for rid, pct in stress["first_failure_uplift_pct"].items():
        assert pct is not None
        below = rational.run(net, T, (pct - 1) / 100, mode="check", fixed=secs)
        at = rational.run(net, T, pct / 100, mode="check", fixed=secs)
        assert rid not in pipeline.failing_reaches(below)
        assert rid in pipeline.failing_reaches(at)


def test_swmm_flooding_grows_with_uplift():
    rows = read_csv("uplift_sweep_swmm.csv")
    vol = [float(r["flood_volume_m3"]) for r in rows]
    assert all(b >= a for a, b in zip(vol, vol[1:]))


def test_stress_csv_consistent_with_summary(stress):
    rows = read_csv("stress_reaches.csv")
    for key, sc in stress["scenarios"].items():
        mine = [r for r in rows if r["scenario"] == key]
        assert len(mine) == 11
        fails = sorted(r["reach"] for r in mine if r["fails_existing"])
        assert fails == sc["rational_failing_reaches"]
        assert max(float(r["utilisation_existing"]) for r in mine) == pytest.approx(
            sc["max_utilisation_existing"], abs=1e-3)
