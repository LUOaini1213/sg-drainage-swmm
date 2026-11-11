"""Tide data, interpolation and the storm-aligned outfall boundary.

The full table of predictions is not in the repository (see sgdrain/tide.py), so
the algorithm tests run on a made-up table, and the data tests on the committed
extract.  One test compares the extract with the full table and runs only where a
local copy of the table exists.
"""
import hashlib
import importlib.util
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sgdrain import coastal, hyetograph, pipeline, tide, tide_pipeline
from conftest import read_json

REPO = Path(__file__).resolve().parents[1]


def made_up_table(n: int = 64) -> list[tide.Extreme]:
    """Alternating low and high waters with irregular spacing and heights.
    Invented numbers, not predictions; the top height is reached more than once."""
    ev, t = [], datetime(2030, 1, 1, 2, 30)
    for k in range(n):
        high = k % 2 == 1
        h = 2.4 + 0.1 * ((k * 7) % 9) if high else 0.3 + 0.1 * ((k * 5) % 11)
        ev.append(tide.Extreme(t, round(h, 1), "H" if high else "L"))
        t += timedelta(minutes=300 + 37 * ((k * 3) % 5) + (95 if high else 0))
    tide.check_sequence(ev)
    return ev


@pytest.fixture(scope="module")
def ev():
    return made_up_table()


@pytest.fixture(scope="module")
def ex():
    return tide.load_extract()


def test_extract_is_the_documented_one(ex, net):
    raw = json.loads(tide.EXTRACT.read_text(encoding="utf-8"))
    assert raw["table_sha256"] in (REPO / "docs" / "sources.md").read_text(encoding="utf-8")
    st = ex.stats
    assert st["n_extremes"] == 236 and st["n_high"] == st["n_low"] == 118
    assert st["first"] == "2026-11-01T04:18" and st["last"] == "2026-12-31T23:01"
    assert round(ex.mean_level_cd, 4) == st["mean_level_cd"]
    # the window: low water, the highest high water, low water; nothing more
    assert [e.kind for e in ex.events] == ["L", "H", "L"]
    for e in ex.events:
        assert e.height_cd == pytest.approx(round(e.height_cd / tide.HEIGHT_RESOLUTION_M)
                                            * tide.HEIGHT_RESOLUTION_M, abs=1e-9)
        assert 0.0 <= e.height_cd <= 4.0
    # ... and it covers the whole simulated run
    hw = tide.highest_high_water(ex.events)
    t0 = hw.time - timedelta(minutes=tide_pipeline.design_peak_minute(net))
    assert ex.events[0].time <= t0
    assert ex.events[-1].time >= t0 + timedelta(minutes=tide_pipeline.SIM_MIN)
    # the full table must not come back into the repository's data folder
    assert not [p.name for p in (REPO / "data").glob("tide_predictions*")]


def test_load_extract_rejects_inconsistent_files(tmp_path):
    raw = json.loads(tide.EXTRACT.read_text(encoding="utf-8"))
    p = tmp_path / "x.json"
    bad = json.loads(json.dumps(raw))
    bad["window"][1]["height_m_cd"] = 3.3
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="highest high water"):
        tide.load_extract(p)
    bad = json.loads(json.dumps(raw))
    bad["mean_level_cd"] = raw["mean_level_cd"] + 0.01
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="mean level"):
        tide.load_extract(p)
    bad = json.loads(json.dumps(raw))
    bad["window"][2]["type"] = "H"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        tide.load_extract(p)
    p.write_text(json.dumps(raw))
    assert tide.load_extract(p) == tide.load_extract()


def test_extract_matches_the_full_table_where_a_local_copy_exists():
    if not tide.LOCAL_TABLE.exists():
        pytest.skip("the full tide table is not redistributed; this check needs a local copy")
    raw = json.loads(tide.EXTRACT.read_text(encoding="utf-8"))
    assert hashlib.sha256(tide.LOCAL_TABLE.read_bytes()).hexdigest() == raw["table_sha256"]
    spec = importlib.util.spec_from_file_location("make_tide_extract",
                                                  REPO / "scripts" / "make_tide_extract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.extract_from(tide.LOCAL_TABLE) == raw
    full = tide.load()
    assert len(full) == 236
    for a, b in zip(full, full[1:]):
        assert timedelta(hours=3) < b.time - a.time < timedelta(hours=9)


def test_load_rejects_bad_sequences(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("date,time,height_m_cd,type\n2026-01-01,00:00,3.0,H\n2026-01-01,06:00,2.5,H\n")
    with pytest.raises(ValueError):
        tide.load(p)
    p.write_text("date,time,height_m_cd,type\n2026-01-01,00:00,1.0,H\n2026-01-01,06:00,2.5,L\n")
    with pytest.raises(ValueError):
        tide.load(p)
    p.write_text("date,time,height_m_cd,type\n2026-01-01,06:00,2.5,H\n2026-01-01,00:00,1.0,L\n")
    got = tide.load(p)                                          # rows are put in time order
    assert [e.kind for e in got] == ["L", "H"] and got[0].height_cd == 1.0


def test_half_cosine_between_extremes(ev):
    for a, b in zip(ev[:60], ev[1:61]):
        assert tide.level_at(ev, a.time) == pytest.approx(a.height_cd, abs=1e-12)
        assert tide.level_at(ev, b.time) == pytest.approx(b.height_cd, abs=1e-12)
        mid = a.time + (b.time - a.time) / 2
        assert tide.level_at(ev, mid) == pytest.approx(0.5 * (a.height_cd + b.height_cd), abs=1e-12)
        q = a.time + (b.time - a.time) / 4       # a quarter of the way: (1 - cos(pi/4)) / 2
        expect = a.height_cd + (b.height_cd - a.height_cd) * (1 - math.cos(math.pi / 4)) / 2
        assert tide.level_at(ev, q) == pytest.approx(expect, abs=1e-12)
        vals = [tide.level_at(ev, a.time + (b.time - a.time) * k / 20) for k in range(21)]
        steps = [y - x for x, y in zip(vals, vals[1:])]
        assert all(s * (b.height_cd - a.height_cd) >= -1e-12 for s in steps)   # monotone
    with pytest.raises(ValueError):
        tide.level_at(ev, ev[0].time - timedelta(minutes=1))
    with pytest.raises(ValueError):
        tide.level_at(ev, ev[-1].time + timedelta(minutes=1))


def test_mean_level_is_the_exact_time_mean(ev):
    # independent: trapezoidal integration of the interpolated curve on a 1-minute grid
    t = ev[0].time
    vals = []
    while t <= ev[-1].time:
        vals.append(tide.level_at(ev, t))
        t += timedelta(minutes=1)
    assert t - timedelta(minutes=1) == ev[-1].time              # the grid ends on the last extreme
    num = sum(0.5 * (x + y) for x, y in zip(vals, vals[1:]))
    numeric = num / (len(vals) - 1)
    assert tide.mean_level(ev) == pytest.approx(numeric, abs=2e-5)
    # it is a time-weighted mean, not the plain average of the extremes
    plain = sum(e.height_cd for e in ev) / len(ev)
    assert abs(tide.mean_level(ev) - plain) > 1e-3
    # two extremes: the mean of a half cosine is the average of its ends
    two = [tide.Extreme(datetime(2030, 1, 1), 1.0, "L"), tide.Extreme(datetime(2030, 1, 1, 6), 3.0, "H")]
    assert tide.mean_level(two) == pytest.approx(2.0, abs=1e-12)


def test_highest_high_water(ev, ex):
    hw = tide.highest_high_water(ev)
    tops = [e for e in ev if e.kind == "H" and e.height_cd == max(x.height_cd for x in ev)]
    assert len(tops) > 1 and hw == tops[0] and hw.time < tops[-1].time     # earliest of the tied waters
    assert all(e.height_cd <= hw.height_cd for e in ev)
    assert tide.stats(ev)["n_highest_hw"] == len(tops)
    # the published table: 3.4 m CD, reached twice; the earlier one is used
    real = tide.highest_high_water(ex.events)
    assert real.kind == "H" and real.height_cd == 3.4 == ex.stats["highest_hw_cd"]
    assert real.time == datetime(2026, 12, 26, 12, 1)
    assert ex.stats["highest_hw_time"] == "2026-12-26T12:01" and ex.stats["n_highest_hw"] == 2


def test_stats_of_a_table(ev):
    st = tide.stats(ev)
    hw = [e.height_cd for e in ev if e.kind == "H"]
    lw = [e.height_cd for e in ev if e.kind == "L"]
    assert (st["n_extremes"], st["n_high"], st["n_low"]) == (64, 32, 32)
    assert st["first"] == "2030-01-01T02:30" and st["last"] == ev[-1].time.isoformat(timespec="minutes")
    assert st["mean_hw_cd"] == round(sum(hw) / 32, 4) and st["mean_lw_cd"] == round(sum(lw) / 32, 4)
    assert st["lowest_lw_cd"] == min(lw) and st["highest_hw_cd"] == max(hw)
    assert st["mean_level_cd"] == round(tide.mean_level(ev), 4)


def test_bracketing_and_build_extract(ev):
    hw = tide.highest_high_water(ev)
    start = hw.time - timedelta(minutes=57.5)
    end = start + timedelta(minutes=240)
    win = tide.bracketing(ev, start, end)
    i = ev.index(win[0])
    assert win == ev[i:i + len(win)]                             # consecutive
    assert win[0].time <= start < win[1].time                    # and no more than needed
    assert win[-2].time < end <= win[-1].time
    assert hw in win
    with pytest.raises(ValueError):
        tide.bracketing(ev, ev[0].time - timedelta(minutes=1), end)
    with pytest.raises(ValueError):
        tide.bracketing(ev, start, ev[-1].time + timedelta(minutes=1))
    d = tide.build_extract(ev, 57.5, 240)
    assert d["stats"] == tide.stats(ev) and d["mean_level_cd"] == tide.mean_level(ev)
    rows = [(r["date"], r["time"], r["height_m_cd"], r["type"]) for r in d["window"]]
    assert rows == [(e.time.strftime("%Y-%m-%d"), e.time.strftime("%H:%M"), e.height_cd, e.kind)
                    for e in win]
    # what makes an extract enough: the tide curve of the run, from the window alone,
    # is the curve from the whole table
    assert tide.aligned_curve(win, hw, 57.5, 240, 5) == tide.aligned_curve(ev, hw, 57.5, 240, 5)
    # a longer run needs a longer window
    assert len(tide.build_extract(ev, 57.5, 900)["window"]) > len(d["window"])


def test_storm_peak_and_aligned_curve(ex, net):
    ev = ex.events
    hy = hyetograph.alternating_block(10, pipeline.STORM_DURATION_MIN, pipeline.STORM_DT_MIN)
    peak = tide_pipeline.storm_peak_minute(hy, pipeline.STORM_DT_MIN)
    assert peak == 57.5 == tide_pipeline.design_peak_minute(net)   # centre of block 11 of 24
    hw = tide.highest_high_water(ev)
    curve = tide.aligned_curve(ev, hw, peak, 240, 5)
    assert [t for t, _ in curve] == list(range(0, 245, 5))
    t0 = hw.time - timedelta(minutes=peak)
    for t, h in curve:
        assert h == pytest.approx(tide.level_at(ev, t0 + timedelta(minutes=t)), abs=1e-12)
    # high water falls between the samples at 55 and 60 min, both just under it
    top = max(curve, key=lambda c: c[1])
    assert top[0] in (55, 60) and hw.height_cd - 1e-3 < top[1] < hw.height_cd


def test_stage_series_datum_and_slr(net, ex):
    ctx = tide_pipeline.tide_context(net)
    assert ctx["mean_cd"] == ex.mean_level_cd
    assert ctx["events"] == ex.events and ctx["stats"] == ex.stats
    assert ctx["hw"] == tide.highest_high_water(ex.events)
    s0 = tide_pipeline.stage_series(ctx, 0.0, 4.0)
    s1 = tide_pipeline.stage_series(ctx, 0.7, 4.0)
    s2 = tide_pipeline.stage_series(ctx, 0.0, 3.5)
    for (t, a), (_, b), (_, c), (_, h) in zip(s0, s1, s2, ctx["curve_cd"]):
        assert a == pytest.approx(ctx["of_ground_local"] - 4.0 + h - ctx["mean_cd"], abs=1e-12)
        assert b - a == pytest.approx(0.7, abs=1e-12)        # rise adds to the whole curve
        assert c - a == pytest.approx(0.5, abs=1e-12)        # lower ground = higher sea
    sh = tide_pipeline.shifted_series(ctx, -0.15)
    assert max(z for _, z in sh) == pytest.approx(ctx["of_ground_local"] - 0.15, abs=1e-12)
    for (_, a), (_, b) in zip(s0, sh):
        assert b - a == pytest.approx(sh[0][1] - s0[0][1], abs=1e-12)   # same shape


def test_tidal_outfall_configuration():
    series = [(0, 7.9), (5, 8.0)]
    open_ = tide_pipeline.tidal_outfall(series, gated=False)
    gated = tide_pipeline.tidal_outfall(series, gated=True)
    assert open_["type"] == gated["type"] == "TIMESERIES"
    assert open_["init_level"] == 7.9 and not open_["gated"]
    assert gated["gated"] and "init_level" not in gated


def test_committed_tide_inputs(ex, net):
    t = read_json("tide_inputs.json")["tide"]
    for k, v in ex.stats.items():
        assert t[k] == v
    assert t["hw_above_mean_m"] == round(3.4 - ex.mean_level_cd, 3)
    assert t["mean_hw_above_mean_m"] == round(ex.stats["mean_hw_cd"] - ex.mean_level_cd, 3)
    d = read_json("tide_inputs.json")["datum"]
    assert d["outfall_ground_shd"] == coastal.OUTFALL_GROUND_SHD_BASE
    assert d["hw_now_shd"] == round(coastal.cd_to_shd(3.4, ex.mean_level_cd), 3)
    assert d["outfall_ground_local"] == net.nodes["OF"].ground
