# sg-drainage-swmm

**Screening-level surface-water drain design and check, following PUB's Code of Practice on Surface Water Drainage, on a SYNTHETIC catchment.**

> **Read this first.** This is a personal learning project. The catchment, levels and land use are invented. It is not a PUB-approved design, not a submission, and not professional engineering advice. Drain design in Singapore is done and endorsed by a Qualified Person / Professional Engineer under the COP and PUB's requirements. The COP itself is not redistributed here: it is referenced (see [docs/sources.md](docs/sources.md)).

<!-- README.md is generated from docs/README.template.md by scripts/run_all.py. Do not edit README.md by hand. -->

## What it does

1. **Catchment.** A 12.6 ha synthetic residential estate: 11 sub-catchments, 11 open U-drain reaches (1020 m) along a road grid, one outfall. Runoff coefficients are area-weighted from the COP land-use classes (C = 0.64 to 0.91).
2. **Rational-method design** per COP Clause 7: Qr = C I A / 360, IDF from COP Appendix 4 (digitised, see below), 10-year return period (Clause 7.1.3, catchment under 100 ha), tc = overland time + drain flow time iterated to a fixed point, and the smallest rectangular concrete section that meets Manning capacity with 15% freeboard, 1.0 to 3.0 m/s and Froude number at most 0.8.
3. **Hydraulic check in EPA SWMM 5.2** (official engine via `swmm-toolkit`): the same network, dynamic-wave routing, a 120-minute alternating-block design storm built from the same IDF curve.
4. **Stress test:** the design sizes under a climate uplift (both ends of the range published for Singapore's Third National Climate Change Study) and under the 100-year storm; which reaches fail, the minimum upsizing that restores COP compliance, and what SWMM says about it.
5. **Drawing-like outputs:** a plan with reach IDs and utilisation colours, and a long-section of the main drain.
6. **Tide and sea-level rise at the outfall:** the free outfall is replaced by the published tide (MPA predictions) raised by official sea-level-rise figures (Third National Climate Change Study, PUB Code of Practice on Coastal Protection), for the design storm and every stress storm. It reports which reaches lose the COP freeboard, how far the backwater reaches, and screening-level responses: outfall level, drain upsizing, flap gate, pump and sump. See [Tide and sea-level rise](#tide-and-sea-level-rise-at-the-outfall).

## Headline numbers

All values below are generated from files in [`results/`](results/) by `scripts/run_all.py`.

| | |
|---|---|
| Design storm | 10-year, IDF from COP Appendix 4; alternating-block hyetograph, 5-min blocks, 113.8 mm in 120 min, peak block 215.6 mm/hr |
| Reaches designed | 11, all meeting the COP checks used: yes; tc iteration converged for all: yes (at most 4 iterations) |
| Max capacity utilisation (Qr / capacity at 0.85 D) | 0.997 (reach E1); range 0.856 to 0.997 |
| Outfall design flow | 4.606 m3/s at tc = 18.6 min, I = 161.8 mm/hr, section 1.9 m x 1.2 m |
| SWMM peak / rational Qr | 1.25 to 1.36 across the reaches (outfall 6.253 vs 4.606 m3/s) |
| SWMM, design storm, design sizes | overtopping at 6 nodes, 230 m3 in total; water enters the COP freeboard in 11 of 11 reaches |
| SWMM continuity error | design run: runoff -0.027%, routing -0.127%; largest magnitude over all 360 SWMM runs: 0.495% (test threshold 1%) |
| Headroom of the design sizes | the first reach breaks a COP criterion at +1% intensity, the last at +17% |
| 100-year storm | 11 of 11 reaches fail (max utilisation 1.39); SWMM overtopping 1647 m3; minimum rational upsizing: 11 reaches, +28% drain volume |
| 10-year +92% (bounding climate case) | 11 of 11 reaches fail (max utilisation 1.92); SWMM overtopping 4690 m3; minimum rational upsizing: +62.9% drain volume |
| Tide and sea-level rise, outfall ground at 4.0 m SHD (assumption) | today's highest predicted high water (1.46 m SHD) plus up to 2.15 m of rise stays below the level that costs freeboard: no reach loses the COP freeboard and SWMM overtopping changes by 0 m3 |
| Highest outfall water level that keeps the COP freeboard | 3.82 m SHD, 0.18 m below the outfall ground; 2.36 m above today's highest predicted high water |
| Sea at the outfall ground (sweep) | 4 reaches lose the freeboard, backwater 164 m up the main drain, SWMM +130 m3; no drain upsizing restores the freeboard; a pump of 4.69 m3/s with a 756 m3 sump behind a shut gate brings SWMM back to the free-outfall result |

The main finding is the gap between the two methods, not the drain sizes. The COP rational method gives the smallest compliant sections. Under its own design storm, SWMM shows those sections running full and overtopping at a few nodes. That gap comes from assumptions the COP leaves open, explained in [SWMM check](#swmm-check).

## How to run

Python 3.11. Everything installs into a local `.venv`.

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/run_all.py       # design, SWMM, stress test, figures, README
pytest                          # tests (offline)
python mutation/run_mutants.py  # optional: mutation test of the test suite
```

`scripts/run_all.py` rewrites everything under `results/` and regenerates this README from `docs/README.template.md`. SWMM runs in a temporary directory, so `.rpt` and `.out` files never land in the repo. The `.inp` models are kept in `results/models/` and open in the EPA SWMM GUI.

The IDF table in `data/` was produced by `tools/digitize_idf.py` from a locally downloaded copy of the COP PDF (`pip install -r requirements-tools.txt`; the script checks the PDF's SHA-256). The pipeline and tests only read the committed CSV.

## Design table (rational method, 10-year)

| Reach | Nodes | L (m) | Slope | A (ha) | C | tc (min) | I (mm/hr) | Qr (m3/s) | W x D (m) | y/D | V (m/s) | Fr | Util. | COP checks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | J1->J2 | 120 | 1:300 | 3.60 | 0.746 | 16.2 | 169.6 | 1.266 | 1.1 x 0.8 | 0.83 | 1.73 | 0.68 | 0.97 | yes |
| B1 | B1->B2 | 75 | 1:250 | 0.90 | 0.853 | 10.9 | 189.1 | 0.403 | 0.6 x 0.6 | 0.82 | 1.37 | 0.63 | 0.95 | yes |
| B2 | B2->J2 | 75 | 1:250 | 1.80 | 0.853 | 11.7 | 186.4 | 0.795 | 1.0 x 0.6 | 0.80 | 1.65 | 0.76 | 0.93 | yes |
| C1 | C1->C2 | 75 | 1:341 | 0.90 | 0.853 | 11.0 | 188.7 | 0.402 | 0.7 x 0.6 | 0.78 | 1.23 | 0.58 | 0.89 | yes |
| C2 | C2->J3 | 75 | 1:357 | 1.80 | 0.853 | 11.9 | 185.7 | 0.792 | 1.1 x 0.6 | 0.83 | 1.44 | 0.65 | 0.97 | yes |
| D1 | D1->D2 | 75 | 1:203 | 0.90 | 0.853 | 10.8 | 189.4 | 0.404 | 0.6 x 0.6 | 0.75 | 1.49 | 0.71 | 0.86 | yes |
| D2 | D2->J4 | 75 | 1:197 | 1.80 | 0.853 | 11.5 | 186.9 | 0.797 | 0.8 x 0.7 | 0.79 | 1.79 | 0.77 | 0.92 | yes |
| E1 | E1->J4 | 150 | 1:395 | 1.80 | 0.735 | 16.9 | 167.0 | 0.614 | 0.8 x 0.7 | 0.85 | 1.29 | 0.54 | 1.00 | yes |
| M2 | J2->J3 | 120 | 1:300 | 5.40 | 0.782 | 17.2 | 166.1 | 1.947 | 1.2 x 1.0 | 0.85 | 1.92 | 0.66 | 1.00 | yes |
| M3 | J3->J4 | 120 | 1:300 | 7.20 | 0.799 | 18.2 | 163.1 | 2.607 | 1.5 x 1.0 | 0.84 | 2.07 | 0.72 | 0.98 | yes |
| M4 | J4->OF | 60 | 1:300 | 12.60 | 0.813 | 18.6 | 161.8 | 4.606 | 1.9 x 1.2 | 0.84 | 2.39 | 0.76 | 0.99 | yes |

`Util.` = Qr / Qc, where Qc is Manning capacity with the water surface at 0.85 D, i.e. keeping the COP freeboard. Sub-catchment runoff enters at the upstream node of the reach it drains to. All invert gradients follow the ground (gradient changes needed: 0). Full columns, including the convergence residual of the tc iteration, are in [`results/design_table.csv`](results/design_table.csv). Invert and cope levels are in [`results/design_levels.csv`](results/design_levels.csv).

![Plan](results/figures/plan_utilisation.png)

![Long-section](results/figures/long_section_main.png)

Design sensitivity ([`results/sensitivity_design.json`](results/sensitivity_design.json)):

- Overland time is the COP's widest open choice (Clause 7.1.4 allows 5 to 15 min). Setting it to the bottom of that range for every sub-catchment raises the outfall flow by 20.8% and changes 9 of 11 sections. Setting it to the top of the range changes the outfall flow by -1% and changes 5 sections.
- The IDF digitisation has a one-pixel reading resolution of about 0.51% in intensity. Shifting all intensities by minus or plus one percent changes 1 and 3 sections respectively.

## SWMM check

| Reach | Rational Qr (m3/s) | SWMM peak (m3/s) | SWMM / rational | Rational y/D | SWMM max y/D | SWMM max V (m/s) |
|---|---|---|---|---|---|---|
| M1 | 1.266 | 1.630 | 1.29 | 0.83 | 1.00 | 1.88 |
| B1 | 0.403 | 0.520 | 1.29 | 0.81 | 1.00 | 1.45 |
| B2 | 0.795 | 1.048 | 1.32 | 0.80 | 1.00 | 1.76 |
| C1 | 0.402 | 0.528 | 1.31 | 0.78 | 0.99 | 1.27 |
| C2 | 0.792 | 1.013 | 1.28 | 0.83 | 1.00 | 1.58 |
| D1 | 0.404 | 0.527 | 1.31 | 0.75 | 0.95 | 1.54 |
| D2 | 0.797 | 1.052 | 1.32 | 0.79 | 0.94 | 2.01 |
| E1 | 0.614 | 0.773 | 1.26 | 0.85 | 0.95 | 1.56 |
| M2 | 1.948 | 2.438 | 1.25 | 0.85 | 1.00 | 2.06 |
| M3 | 2.607 | 3.393 | 1.30 | 0.84 | 0.97 | 2.45 |
| M4 | 4.606 | 6.253 | 1.36 | 0.84 | 0.90 | 3.04 |

SWMM peaks are higher than the rational Qr in every reach (ratio 1.25 to 1.36). The difference is expected, and most of it can be traced at sub-catchment level ([`results/subcatchment_swmm_vs_rational.csv`](results/subcatchment_swmm_vs_rational.csv)):

| Sub-catchment | Land use | COP C | to (min) | Rational Q (m3/s) | SWMM peak (m3/s) | Ratio | Duration factor | Runoff factor |
|---|---|---|---|---|---|---|---|---|
| S01 | residential | 0.85 | 10 | 0.821 | 1.060 | 1.29 | 1.12 | 1.15 |
| S02 | residential_park | 0.64 | 15 | 0.556 | 0.870 | 1.56 | 1.24 | 1.26 |
| S03 | residential | 0.85 | 10 | 0.411 | 0.530 | 1.29 | 1.12 | 1.15 |
| S04 | residential | 0.85 | 10 | 0.411 | 0.530 | 1.29 | 1.12 | 1.15 |
| S05 | residential | 0.85 | 10 | 0.411 | 0.530 | 1.29 | 1.12 | 1.15 |
| S06 | residential | 0.85 | 10 | 0.411 | 0.530 | 1.29 | 1.12 | 1.15 |
| S07 | residential | 0.85 | 10 | 0.411 | 0.530 | 1.29 | 1.12 | 1.15 |
| S08 | residential | 0.85 | 10 | 0.411 | 0.530 | 1.29 | 1.12 | 1.15 |
| S09 | school | 0.73 | 15 | 0.639 | 0.970 | 1.52 | 1.24 | 1.22 |
| S10 | commercial | 0.91 | 5 | 0.489 | 0.540 | 1.10 | 1.00 | 1.10 |
| S11 | commercial | 0.91 | 5 | 0.489 | 0.540 | 1.10 | 1.00 | 1.10 |

- **Duration factor** = peak 5-minute block intensity / IDF intensity at the overland time used in the rational method. The rational method applies the intensity for a duration equal to tc, with a 5 to 15 min overland time. SWMM's surface runoff from short, smooth paved areas responds within minutes, so it picks up the 5-minute peak that the alternating-block storm contains. Range: 1.00 to 1.24.
- **Runoff factor** = (SWMM peak runoff / peak rainfall rate on the area) / COP C. SWMM's losses (depression storage plus Green-Ampt infiltration in a clay-loam soil) remove less water at the peak than the COP coefficients imply. Range: 1.10 to 1.26. Event runoff coefficients in SWMM are 0.893 to 0.977, against COP C of 0.64 to 0.91.
- In the network, routing through the drains attenuates and offsets the sub-catchment peaks, which fits the reach ratios lying between the sub-catchment extremes. Where a drain runs full, SWMM also caps the flow: `SWMM max y/D` reaches the full drain depth, and the excess overtops at the upstream node.
- SWMM's peak velocity also exceeds the COP's 3.0 m/s limit in reach(es) M4. The rational check at normal depth does not show this.
- A sandier soil (sandy loam, SWMM manual Table A.2) lowers the event runoff coefficient to 0.864 but barely moves the outfall peak (6.217 m3/s). Overtopping falls to 109 m3. Losses matter less than timing for these peaks.

**SWMM-led upsizing (heuristic).** Repeatedly enlarging the most downstream failing reaches by one catalogue step, until SWMM shows no overtopping and no reach deeper than 0.85 D, takes 11 reaches and +28.7% drain volume for the design storm. The heuristic only targets depth: its final peak velocity is 3.00 m/s against the COP limit of 3.0 m/s. It is not proven minimal.

![SWMM vs rational](results/figures/swmm_vs_rational.png)

Continuity: runoff -0.027% and flow routing -0.127% for the design run. Across all 360 SWMM runs the largest magnitude is 0.495% ([`results/swmm_run_log.json`](results/swmm_run_log.json)). The tests require below 1%.

## Stress test

Uplifts are applied multiplicatively to the 10-year IDF intensities. The +6% and +92% values are the two ends of the range the V3 news release gives for extreme *daily* rainfall in April and May. Applying a daily-rainfall change to short-duration intensities is this project's assumption. The upper end is treated as a bounding case, not a projection for design. The 100-year case uses the COP's own 100-year curve.

| Scenario | Max utilisation (design sizes) | Reaches failing (rational) | SWMM overtopping (design sizes) | Minimum rational upsizing | SWMM overtopping after rational upsizing | SWMM-led greedy upsizing |
|---|---|---|---|---|---|---|
| 10-yr storm +6% (low end of V3 range) | 1.06 | 7 / 11 | 9 nodes, 387 m3 | 7 reaches, +6.9% | 150 m3 | 11 reaches, +34.2% |
| 10-yr storm +92% (high end of V3 range, bounding) | 1.92 | 11 / 11 | 11 nodes, 4690 m3 | 11 reaches, +62.9% | 450 m3 | 11 reaches, +112.0% |
| 100-yr storm, COP Appendix 4 curve | 1.39 | 11 / 11 | 10 nodes, 1647 m3 | 11 reaches, +28.0% | 368 m3 | 11 reaches, +67.1% |

"Minimum rational upsizing" keeps each reach's gradient and never shrinks a section. It picks the smallest catalogue section that passes every COP check again, and is minimal within the catalogue by construction. Because SWMM peaks run above rational Qr, those sections still overtop in SWMM. The SWMM-led column shows the larger enlargement the dynamic check asks for.

| Reach | Design W x D (m) | Rational upsizing: 10-yr storm +6% (low end of V3 range) | Rational upsizing: 10-yr storm +92% (high end of V3 range, bounding) | Rational upsizing: 100-yr storm, COP Appendix 4 curve |
|---|---|---|---|---|
| M1 | 1.1 x 0.8 | 1.2 x 0.8 | 1.3 x 1.1 | 1.4 x 0.8 |
| B1 | 0.6 x 0.6 | 0.7 x 0.6 | 1.0 x 0.6 | 0.8 x 0.6 |
| B2 | 1.0 x 0.6 | - | 1.2 x 0.8 | 1.1 x 0.7 |
| C1 | 0.7 x 0.6 | - | 0.9 x 0.7 | 0.9 x 0.6 |
| C2 | 1.1 x 0.6 | 1.2 x 0.6 | 1.8 x 0.6 | 1.4 x 0.6 |
| D1 | 0.6 x 0.6 | - | 0.8 x 0.7 | 0.7 x 0.6 |
| D2 | 0.8 x 0.7 | - | 1.0 x 0.9 | 0.9 x 0.8 |
| E1 | 0.8 x 0.7 | 0.9 x 0.7 | 1.3 x 0.7 | 0.9 x 0.8 |
| M2 | 1.2 x 1.0 | 1.3 x 1.0 | 1.8 x 1.1 | 1.4 x 1.1 |
| M3 | 1.5 x 1.0 | 1.6 x 1.0 | 1.9 x 1.3 | 1.6 x 1.2 |
| M4 | 1.9 x 1.2 | 2.0 x 1.2 | 2.2 x 1.7 | 2.1 x 1.4 |

Uplift sweep with the design sizes, in 1% steps for the rational check and 4% steps in SWMM ([`results/uplift_sweep_rational.csv`](results/uplift_sweep_rational.csv), [`results/uplift_sweep_swmm.csv`](results/uplift_sweep_swmm.csv)):

| Reach | Smallest uplift that breaks a COP criterion |
|---|---|
| M1 | +3% |
| B1 | +6% |
| B2 | +9% |
| C1 | +13% |
| C2 | +4% |
| D1 | +17% |
| D2 | +10% |
| E1 | +1% |
| M2 | +1% |
| M3 | +2% |
| M4 | +1% |

![Uplift sweep](results/figures/uplift_sweep.png)

The design sizes have almost no headroom. Smallest-compliant sizing plus a 0.1 m size grid leaves utilisations of 0.856 to 0.997, so any uplift breaks some reach. A real design would choose standard sections, usually with margin.

## Tide and sea-level rise at the outfall

Everything above assumes a free outfall. Here the water level at the outfall follows the sea. Numbers come from [`results/tide_summary.json`](results/tide_summary.json), [`results/tide_scenarios.csv`](results/tide_scenarios.csv), [`results/tide_datum_sensitivity.csv`](results/tide_datum_sensitivity.csv), [`results/tide_level_sweep.csv`](results/tide_level_sweep.csv) and [`results/tide_inputs.json`](results/tide_inputs.json); sources with clause and page numbers are in [docs/sources.md](docs/sources.md).

**Sea level at the outfall.**

- **Tide:** MPA's predicted high and low waters for November and December 2026, as published on NEA's Tide Timings page: 236 values in metres above Chart Datum. The page does not name the station. The table itself is not in this repository, because NEA's website terms do not allow redistribution; [`data/tide_extract_mpa_2026-11_12.json`](data/tide_extract_mpa_2026-11_12.json) holds the statistics quoted here and the three predicted extremes around the highest high water, which are all the runs use. The highest predicted high water is 3.4 m CD (first on 2026-12-26 12:01, Singapore time assumed). The time-mean of the predicted curve is 1.9418 m CD, so that high water stands 1.458 m above the mean (the average predicted high water stands 0.865 m above it). Between predicted extremes the level follows a half cosine. SWMM gets the predicted curve around that high water as a TIMESERIES outfall, with high water at the centre of the storm's peak 5-minute block, i.e. storm peak and spring high water coincide.
- **Sea-level rise**, added to the whole curve, one official figure per scenario, no interpolation: +0.7 m (CPCOP 0.7m RMSLR planning scenario), +1.15 m (V3 SSP5-8.5, 2100, top of likely range), +2.15 m (CPCOP 2.15m RMSLR planning scenario). The CPCOP gives no year for its two planning scenarios. The V3 figure is the top of the likely range at Sultan Shoal, the gauge with the highest projections (V3 Report for Stakeholders, Table 5.10, relative to 1995-2014). The same table gives a Singapore average (median of six gauges) of 0.79 m for SSP5-8.5 by 2100, and 2.12 m as the top of the SSP5-8.5 likely range at Sultan Shoal by 2150.
- **Outfall:** open (the tide enters the drains, which start filled to the tide level) or with a flap gate (the drains start empty and discharge only when they stand above the sea).
- **Not included:** storm surge and waves. PUB's extreme sea levels for the CPCOP, which add surge, are still under review (CPCOP Cl. 4.3, footnote). Official statements put the combined level at up to 5 m above today's mean sea level with storm surge and high tide (MSE, 2026). Under assumptions A1 and A2 that is above the ground at 7 of the 12 nodes of this catchment: a coastal protection question, not a drain one.

**Datum. ASSUMPTIONS, needed because the catchment is synthetic.**

- **A1:** the ground at the outfall node is at 4.0 m SHD, the COP minimum platform level for developments along the southern coast (Cl. 2.1.1(a)(i); also the minimum reclamation level, Cl. 2.3). The local datum is then SHD + 4.6 m: the outfall invert sits at 2.80 m SHD and the ground runs from 4.00 to 5.60 m SHD.
- **A2:** the time-mean of the predicted tide is taken as 0.0 m SHD. SHD is based on the mean sea level at Victoria Dock in 1935-1937 (NCCS). The official Chart Datum to SHD conversion is held by MPA's Hydrographic Division (CPCOP terminology) and was not available. The predictions also cover only two months of the north-east monsoon, so their mean need not be the annual mean.
- Hydraulically only the sea level relative to the drains matters, so both assumptions act through one number: high water minus outfall ground. Lowering the assumed outfall ground by some amount is the same as raising the tide datum, or the sea, by that amount. The sensitivity runs move the outfall ground from 4.5 to 2.5 m SHD, and a sweep moves high water from -2.6 to 0 m relative to the outfall ground.

**Two checks.** SWMM runs each storm against each sea level and compares with the same storm and drains on a free outfall: extra overtopping, newly flooded nodes, and the rise of each node's maximum water level (a node counts as raised at 0.02 m or more; at a node that already overtops, the level is capped at the cope, so extra overtopping shows in volume, not level). The steady check computes backwater curves (standard step, 1 m stations) at the rational design flows with the outfall held at the high-water level, and applies the COP freeboard (Cl. 7.3.4) along every reach. It reports the reaches that lose the freeboard because of the sea, and how far up the main drain the level rises by 0.01 m or more over the free-outfall profile.

### Results at the base assumption

| Sea level at the outfall | High water (m SHD) | vs outfall invert (m) | Reaches losing the COP freeboard (steady) | Backwater up the main drain (m) | SWMM extra overtopping, open / flap-gated (m3) | Largest rise of a node's max level (m) |
|---|---|---|---|---|---|---|
| today's tide (2026 predictions) | 1.46 | 1.34 below | none | 0 | +0 / +0 | 0.000 |
| +0.7 m (CPCOP 0.7m RMSLR planning scenario) | 2.16 | 0.64 below | none | 0 | +0 / +0 | 0.000 |
| +1.15 m (V3 SSP5-8.5, 2100, top of likely range) | 2.61 | 0.19 below | none | 0 | +0 / +0 | 0.000 |
| +2.15 m (CPCOP 2.15m RMSLR planning scenario) | 3.61 | 0.81 above | none | 0 | +0 / +0 | 0.000 |

At the base assumption the sea changes nothing for the design storm. Today's highest predicted high water stands 1.342 m below the outfall invert. With 2.15 m of rise it stands 0.808 m above the invert and reaches into the lower ends of reaches D2, E1, M2, M3, M4, but stays below the water level the design flow itself needs at the outfall. No reach loses the freeboard and no node's maximum level rises. Across all 56 storm, drain-size, sea-level and gate combinations at the base assumption, the largest change in SWMM overtopping is 4 m3 (10-yr storm +92% (high end of V3 range, bounding), rational upsizing, largest node rise 0.002 m):

| Storm | Drain sizes | Outfall drain W x D (m) | Outfall invert (m SHD) | Highest outfall level keeping the COP freeboard (m SHD) | SWMM extra overtopping (m3): today's tide (2026 predictions) | SWMM extra overtopping (m3): +0.7 m (CPCOP 0.7m RMSLR planning scenario) | SWMM extra overtopping (m3): +1.15 m (V3 SSP5-8.5, 2100, top of likely range) | SWMM extra overtopping (m3): +2.15 m (CPCOP 2.15m RMSLR planning scenario) |
|---|---|---|---|---|---|---|---|---|
| 10-yr design storm | design | 1.9 x 1.2 | 2.80 | 3.82 | +0 | +0 | +0 | +0 |
| 10-yr storm +6% (low end of V3 range) | design | 1.9 x 1.2 | 2.80 | fails without tide | +0 | +0 | +0 | +0 |
| 10-yr storm +6% (low end of V3 range) | rational upsizing | 2.0 x 1.2 | 2.80 | 3.82 | +0 | +0 | +0 | +0 |
| 10-yr storm +92% (high end of V3 range, bounding) | design | 1.9 x 1.2 | 2.80 | fails without tide | +0 | +0 | +0 | +0 |
| 10-yr storm +92% (high end of V3 range, bounding) | rational upsizing | 2.2 x 1.7 | 2.30 | 3.75 | +0 | +0 | +0 | +4 |
| 100-yr storm, COP Appendix 4 curve | design | 1.9 x 1.2 | 2.80 | fails without tide | +0 | +0 | +0 | +0 |
| 100-yr storm, COP Appendix 4 curve | rational upsizing | 2.1 x 1.4 | 2.60 | 3.79 | +0 | +0 | +0 | +1 |

Upsizing for heavier rain lowers the level the outfall can tolerate. The +92% upsizing deepens the outfall drain to 2.2 x 1.7 m, so its invert sits lower and its 15% freeboard is larger. Its highest tolerable outfall level is 3.745 m SHD, against 3.82 m SHD for the design sizes.

![Long-section with tide and sea-level rise](results/figures/long_section_tide.png)

### Where the sea starts to matter

The datum sensitivity (design storm, design sizes; each cell is the open-outfall run):

| Outfall ground (m SHD) | today's tide (2026 predictions) | +0.7 m (CPCOP 0.7m RMSLR planning scenario) | +1.15 m (V3 SSP5-8.5, 2100, top of likely range) | +2.15 m (CPCOP 2.15m RMSLR planning scenario) |
|---|---|---|---|---|
| 4.5 | no effect (high water 1.84 m below the outfall invert) | no effect (high water 1.14 m below the outfall invert) | no effect (high water 0.69 m below the outfall invert) | no effect (high water 0.31 m above the outfall invert) |
| 4.0 | no effect (high water 1.34 m below the outfall invert) | no effect (high water 0.64 m below the outfall invert) | no effect (high water 0.19 m below the outfall invert) | no effect (high water 0.81 m above the outfall invert) |
| 3.5 | no effect (high water 0.84 m below the outfall invert) | no effect (high water 0.14 m below the outfall invert) | no effect (high water 0.31 m above the outfall invert) | sea 0.11 m above ground |
| 3.0 | no effect (high water 0.34 m below the outfall invert) | no effect (high water 0.36 m above the outfall invert) | no effect (high water 0.81 m above the outfall invert) | sea 0.61 m above ground |
| 2.5 | no effect (high water 0.16 m above the outfall invert) | no effect (high water 0.86 m above the outfall invert) | sea 0.11 m above ground | sea 1.11 m above ground |

The effect is a threshold. Nothing happens while high water stays below the water level the design flow itself needs at the outfall. The 1.2 m deep outfall drain runs at normal depth just under its freeboard line, so the COP freeboard is gone as soon as the sea passes 0.18 m below the outfall cope, and the land floods from the sea once it passes the ground. The sweep shows where this happens: every sweep level at which anything changed is listed below (all lower levels change nothing).

| High water minus outfall ground (m) | High water at the base assumption (m SHD) | Reaches losing the COP freeboard (steady) | Backwater up the main drain, steady (m) | SWMM extra overtopping, open / flap-gated (m3) | Largest rise of a node's max level (m) | SWMM: furthest main-drain node raised 2 cm or more (m from outfall) | Drain upsizing that restores the freeboard |
|---|---|---|---|---|---|---|---|
| -0.30 | 3.70 | none | 0 | +1 / +1 | 0.000 | 0 | - |
| -0.25 | 3.75 | none | 0 | +2 / +2 | 0.000 | 0 | - |
| -0.20 | 3.80 | none | 0 | +4 / +4 | 0.000 | 0 | - |
| -0.15 | 3.85 | M4 | 60 | +11 / +11 | 0.024 | 60 | infeasible (M4) |
| -0.10 | 3.90 | M4 | 60 | +21 / +21 | 0.048 | 60 | infeasible (M4) |
| -0.05 | 3.95 | M3, M4 | 127 | +35 / +35 | 0.065 | 60 | infeasible (M3, M4) |
| +0.00 | 4.00 | D2, E1, M3, M4 | 164 | +130 / +130 | 0.065 | 60 | infeasible (D2, E1, M3, M4) |

![Sweep of the high-water level](results/figures/tide_level_sweep.png)

**How far upstream the backwater reaches.** At the base assumption, nowhere: the longest steady backwater over all base runs is 0 m, and the largest rise of any node's maximum level in SWMM is 0.002 m. In the sweep the steady backwater first appears when high water comes within 0.15 m of the outfall ground. With the sea at the outfall ground it runs 164 m up the main drain and raises reaches D2, E1, M3, M4; reaches D2, E1, M3, M4 lose the COP freeboard. In SWMM the nodes raised by 0.02 m or more are J4, by up to 0.065 m. The largest difference in overtopping between open and flap-gated runs anywhere in the sweep is 0 m3: a flap gate keeps seawater out of the drains before the storm, but does not help them discharge against a high sea.

### Screening-level responses

These are screening estimates on a synthetic catchment, not designs.

1. **Outfall level.** With the design sizes the outfall water level must stay at or below 3.82 m SHD (0.18 m below the outfall ground) to keep the COP freeboard at the design flow. Put the other way, the lowest outfall ground that keeps a gravity outfall working for each sea level is:

| Sea level | High water (m SHD) | Lowest outfall ground keeping the COP freeboard (m SHD) | Lowest outfall ground with no SWMM rise of 2 cm or more (m SHD, sweep steps of 0.05 m) | Margin if the outfall ground is at the COP minimum platform level (m) |
|---|---|---|---|---|
| today's tide (2026 predictions) | 1.46 | 1.64 | 1.66 | +2.36 |
| +0.7 m (CPCOP 0.7m RMSLR planning scenario) | 2.16 | 2.34 | 2.36 | +1.66 |
| +1.15 m (V3 SSP5-8.5, 2100, top of likely range) | 2.61 | 2.79 | 2.81 | +1.21 |
| +2.15 m (CPCOP 2.15m RMSLR planning scenario) | 3.61 | 3.79 | 3.81 | +0.21 |

   With the outfall ground at the COP minimum platform level, the margin over the 2.15 m planning scenario's predicted high water is 0.21 m, before any storm surge.
2. **Drain upsizing under tailwater: does not work here.** The search tries every larger catalogue section (width and depth never reduced, gradient kept, normal-depth COP checks still met), reach by reach from the outfall up. At every sweep level that costs freeboard it finds none (last column of the sweep table). The sea fixes the water level at the outfall. A wider drain only flattens the water surface further up. A deeper drain keeps its cope at the ground, so its invert drops and its 15% freeboard grows while the free height above the sea does not.
3. **Flap gate.** Keeps the sea out of the drains between storms, but on its own it changes nothing at the storm peak (above).
4. **Pump and sump behind a shut gate.** When the sea stands above the outfall level the drains can tolerate, everything that reaches the outfall has to be pumped or stored. For a steady rational check a pump of at least the outfall design flow, 4.606 m3/s, holds the outfall at the free-outfall level. For the SWMM storms, the storage a sump needs for a given pump comes from the mass curve of the free-outfall inflow (gate shut for the whole storm, drain storage ignored):

| Storm | Drain sizes | Peak inflow = pump with no sump (m3/s) | Inflow volume (m3) | Sump for a pump at 90% of peak (m3) | Sump for a pump at 75% of peak (m3) | Sump for a pump at 60% of peak (m3) | Sump for a pump at 50% of peak (m3) |
|---|---|---|---|---|---|---|---|
| 10-yr design storm | design | 6.25 | 13391 | 168 | 756 | 1622 | 2415 |
| 10-yr storm +6% (low end of V3 range) | design | 6.34 | 14095 | 198 | 832 | 1793 | 2646 |
| 10-yr storm +6% (low end of V3 range) | rational upsizing | 6.78 | 14331 | 201 | 822 | 1723 | 2559 |
| 10-yr storm +92% (high end of V3 range, bounding) | design | 6.79 | 22100 | 540 | 2088 | 4099 | 5763 |
| 10-yr storm +92% (high end of V3 range, bounding) | rational upsizing | 12.34 | 26334 | 316 | 1427 | 3071 | 4606 |
| 100-yr storm, COP Appendix 4 curve | design | 6.64 | 17684 | 315 | 1329 | 2728 | 3897 |
| 100-yr storm, COP Appendix 4 curve | rational upsizing | 8.75 | 18962 | 251 | 1069 | 2294 | 3413 |

   For scale only, COP Cl. 10.1(a), written for pumped drainage of underground facilities and not for estate outfalls, would ask 5.25 m3/s for this 12.6 ha catchment. SWMM check, design storm, sea held at the outfall ground behind a shut flap gate: with no pump, overtopping rises by 131 m3. With a pump of 4.688 m3/s (75% of peak inflow) and a 756 m3 sump (732 m2 over 1.033 m), it changes by -5 m3 and no node's maximum level rises by more than 0.002 m: the free-outfall result is restored. Pump head, start-up and standby pumps are not modelled.

**Joint probability.** Every run puts the storm peak on the highest predicted high water of the two months. The COP does not specify a tailwater for drain design, and the CPCOP's extreme sea levels, which would carry the joint probability of surge and tide, are not yet published. A design storm arriving exactly at the year's highest spring tide is much rarer than the storm alone, so for the tide itself the pairing is conservative. Storm surge, which would raise the sea, is left out, and the V3 rise is counted from its 1995-2014 baseline on top of 2026 predictions, which double-counts the rise since then. These runs locate the threshold. They do not say how often it is crossed.

## Method

- **Rational formula** (COP Cl. 7.1.1): Qr = C I A / 360 (m3/s, mm/hr, ha). C is weighted by area from the Cl. 7.1.2 classes: roads/paved 1.00, urban 0.90, vegetated/pervious 0.45.
- **Return period** (Cl. 7.1.3): 10 years for a catchment under 100 ha.
- **IDF**: the COP gives the IDF relationship only as a chart (Appendix 4). `tools/digitize_idf.py` reads the embedded chart image, calibrates both log axes from the detected grid lines, and traces all eight return-period curves. It tabulates 27 durations from 5 to 600 min. Reading resolution is about 0.51% per pixel, and the largest local-fit residual is 1.33 px. Between tabulated durations, values are interpolated linearly on log-log axes.
- **Time of concentration** (Cl. 7.1.4): tc = to + td. The overland time to is taken per land use within the COP's 5 to 15 min range (5, 10, 15 min). The drain time td comes from the Manning velocity in the chosen section. Because the section depends on Qr, which depends on tc, each reach is iterated to a fixed point (tolerance in `sgdrain/rational.py`).
- **Sizing** (Cl. 7.2.2, 7.2.3, 7.3.1 to 7.3.4, 4.3.1): rectangular open concrete drain, n = 0.015, steady uniform flow at normal depth. A section is accepted if y is at most 0.85 D, V is between 1.0 and 3.0 m/s, and Fr is at most 0.8. Width and depth must each be at least 600 mm, and sections come from a 0.1 m catalogue (0.6 to 3 m wide, 0.6 to 2 m deep). The smallest area wins. The invert follows the ground slope; a list of alternative gradients is tried only if no section fits.
- **Levels**: the drain cope is at or below ground at both ends, and no drain starts above the inverts of the drains flowing into it.
- **Hyetograph**: alternating block (Chow, Maidment & Mays, *Applied Hydrology*, 1988, ch. 14), 5-min blocks over 120 min with the peak in the centre. The central window of k blocks holds the k largest IDF depth increments. The storm therefore reaches at least the IDF depth for every duration up to its length, and exactly that depth where the digitised depth-duration curve is concave. A test checks this.
- **SWMM**: SWMM 5.2 through `swmm-toolkit`, dynamic wave, 1 s routing step. Conduits are open rectangular, invert elevations come from the design, and the outfall is free except in the tide runs. Node overflow level is the highest drain cope at the node, with no ponding: water above it is reported as overtopping (flooding) and lost. Sub-catchment parameters are in [Assumptions](#assumptions).
- **Tide boundary** (`sgdrain/tide.py`, `sgdrain/swmm_model.py`): SWMM TIMESERIES outfall at 5-minute steps from the predicted extremes, half-cosine between them. SWMM takes the larger of the sea level and critical/normal depth at the outfall, so a sea below the outfall invert behaves exactly like a free outfall (a test checks this). Open outfall: the junctions start filled to the sea level. Flap gate: SWMM's gated outfall.
- **Backwater** (`sgdrain/backwater.py`): standard step method on the energy equation with the Manning friction slope averaged over each step, from the outfall upstream, water level continuous through junctions, junction losses ignored. A sea below the normal-depth level leaves the design flow at normal depth; the drawdown towards a free outfall is ignored (conservative). The highest tolerable outfall level is found by bisection.
- **Pump and sump** (`sgdrain/pumpsump.py`): mass-curve (sequent-peak) storage for a constant pump capacity, exact for a piecewise-linear inflow. The SWMM check replaces the outfall node by a storage node of constant area that drains to the sea through a flap-gated outlet and is emptied by a variable-speed pump whose flow reaches capacity over the first few centimetres of sump depth.

## Assumptions

- **Synthetic catchment**: geometry, ground levels (arbitrary local datum, not SHD), land-use split and overland times are invented to look plausible. No public elevation data was used.
- **Lumped inflow**: each sub-catchment discharges at the upstream node of its reach. This is conservative for the rational method and identical in SWMM.
- **Minimum size**: COP Cl. 4.3.1 sets the 600 mm minimum for roadside drains in a *closed* drainage system. It is applied here to every drain.
- **Size catalogue and gradient list**: illustrative. Real roadside drains follow the LTA standard details referenced in COP Cl. 9.1.2 / Drawing No. 1, which were not used.
- **SWMM hydrology** (sources in [docs/sources.md](docs/sources.md)): percent impervious = roads 100%, urban plots 90%, vegetated 0%. Overland flow length is 30 to 60 m depending on land use, and width = area / length. N-imperv 0.011, N-perv 0.15 (SWMM manual Table A.6). Depression storage 1.27 / 2.54 mm (lower end of Table A.5). %Zero-Imperv 25. Green-Ampt clay loam from Table A.2: suction 210.1 mm, Ksat 1.016 mm/hr, initial deficit 0.154. None of this is calibrated.
- **Climate uplift**: one multiplier on every duration, taken from the range given for extreme *daily* rainfall (see Stress test).
- **Datum** (tide runs): A1, outfall ground at the COP minimum platform level for the southern coast; A2, mean of the predicted tide at SHD zero. Both are assumptions, covered by the sensitivity runs and the sweep (see [Tide and sea-level rise](#tide-and-sea-level-rise-at-the-outfall)).
- **Outfall setting**: the drains discharge straight to the sea, as for a drain outfall under COP Cl. 4.11, which also requires the outfall to discharge below the low tide level. A canal or reservoir between the estate and the sea is not modelled.

## Limitations

- Screening only: no structural, geotechnical, utility, maintenance-access or construction checks. No sumps, transitions or bends (COP Cl. 9), no dry-weather-flow channel detail (Cl. 7.3.1, Drawing No. 1), no culverts. The design and the rainfall stress test use a free outfall; tailwater is only in the tide runs.
- Tide runs: the tie between the catchment, SHD and Chart Datum rests on assumptions A1 and A2; the official Chart Datum to SHD conversion and MPA's tabulated tidal levels (for example mean high water springs) were not available. The tide comes from two months of predictions (November and December 2026, north-east monsoon), from a station the source does not name, rounded to 0.1 m. No storm surge, waves or wind set-up; PUB's extreme sea levels for the CPCOP were not available. The V3 rise is added to 2026 predictions although it is measured from 1995-2014. Vertical land movement is left to the V3 figures (relative sea level).
- Joint probability of storm and tide is not modelled: every run pairs the storm peak with the highest predicted high water. No canal, reservoir or tidal-gate operation between the estate and the sea.
- The backwater check uses the rational flows, ignores junction losses and holds the outfall at the high-water level. The pump-sump estimate ignores storage in the drains, pump head, start-up, standby pumps and power; COP Cl. 10.1 requirements for pumped systems are quoted only for scale.
- Cl. 7.1.5 (maximum allowable peak runoff from larger development sites, usually met with on-site detention) is outside this exercise.
- The IDF values are a digitisation of a scanned chart, not PUB tabulated data.
- The rational design and its checks are at normal depth. Backwater appears in SWMM and, for the tide runs, in the steady backwater check.
- SWMM overland-flow and loss parameters are textbook values, not calibrated to any Singapore catchment. The SWMM/rational gap depends on them and on the choice of an alternating-block storm, which nests every duration's peak in one event.
- The SWMM-led upsizing is a greedy heuristic and only looks at depth and overtopping.

## Repository layout

```
data/        synthetic catchment definition, digitised IDF table and its metadata,
             extract of the published tide predictions (MPA via NEA; the full table is not redistributed)
sgdrain/     COP constants (cop.py), Manning (hydraulics.py), IDF, hyetograph,
             rational design/check/upsize, SWMM writer/runner, pipeline, plots, README renderer;
             coastal.py (official sea-level figures, datum assumption), tide.py, backwater.py,
             pumpsump.py, tide_pipeline.py
scripts/     run_all.py - regenerates results/ and README.md;
             make_tide_extract.py - rebuilds the tide extract from a local copy of the table
results/     every number quoted above (CSV/JSON), figures, SWMM .inp models
tools/       digitize_idf.py - IDF chart digitiser (needs a local copy of the COP PDF)
tests/       pytest suite (offline)
mutation/    mutation testing of the test suite and its report
docs/        README template and sources with clause references
```

## Tests

`pytest` runs 124 tests offline. They cover:

- Manning and continuity invariants: capacity monotonic in width, depth and slope, Q = V A, and normal depth as the inverse of Manning.
- Rational-method arithmetic.
- Weighted C and the COP return-period rule.
- tc convergence, with each residual re-checked independently.
- Smallest-section optimality and COP criteria on every reach.
- The alternating-block window property.
- SWMM continuity below 1%, and a re-run of the SWMM design model checked against the committed results.
- Upsizing never shrinks a section and restores compliance.
- Tide and sea level: the official figures pinned to their sources, datum conversions, the tide interpolation and exact time-mean (on a made-up table), the committed tide extract (compared with the full table only where a local copy exists, so not in CI), the storm-aligned boundary, and that a sea below the outfall invert gives exactly the free-outfall SWMM result while a flap gate stops all backflow.
- Backwater: uniform flow is reproduced, the backwater curve against an independent numerical integration of the gradually-varied-flow equation, the highest tolerable outfall level bracketed, and the upsizing search.
- Pump and sump: the mass curve against closed-form results, and a SWMM run with a pump.
- README numbers checked against `results/`.

**Mutation test of the tests** ([`mutation/run_mutants.py`](mutation/run_mutants.py), report in [`results/mutation_report.json`](results/mutation_report.json)). The script plants 46 deliberate bugs, one at a time, in a scratch copy of the repo: 20 in the drain design and 26 in the tide and sea-level code. It first checks that the unmodified suite passes and that every mutant compiles. For the drain design, the first round killed 18 of 20 mutants. The survivors were M13 (minimum self-cleansing velocity not checked), M15 (drain may start above the inverts flowing into it). The second survived because that level constraint never binds in this network. Tests were then added that check each section criterion flag on its own and force the level constraint to bind. The tide and sea-level mutants joined in round 3, where the tests as first written killed 24 of 26. Survivors: T15 (upsizing keeps the old inverts (a deeper drain's cope rises above ground)), T16 (backwater extent counts stations that are not raised). The first was masked: the search re-checks its final network with the correct inverts, so a wrong trial still ended as "infeasible". Nothing recounted the backwater extent from the profiles, so the second went unseen. Tests were then added that require a failed search to report no enlargement and to match a re-run, that recount the extent station by station, and that recompute every committed sweep row. In the same round the design mutant for the SWMM conduit roughness was reported invalid rather than run: the new sump outlet repeats the expression it replaces, so its snippet now names the network conduit line. In the latest round (round 5, 124 tests) the suite killed **46 of 46**: 20 of 20 in the drain design, 26 of 26 in the tide and sea-level code. Survivors: none.

## Sources

Full list with URLs, retrieval dates and clause/table/page references: [docs/sources.md](docs/sources.md). In short:

- PUB, *Code of Practice on Surface Water Drainage*, Seventh Edition (Dec 2018) with amendments under Addendum No. 3 (April 2025). Clauses 4.3.1, 7.1.1 to 7.1.4, 7.2.2, 7.2.3, 7.3.1 to 7.3.4 and Appendix 4.
- US EPA, *Storm Water Management Model User's Manual Version 5.2* (EPA/600/R-22/030, 2022): Tables A.2, A.5 and A.6.
- MSS/MSE joint news release on Singapore's Third National Climate Change Study (V3), 5 January 2024: the range for extreme daily rainfall and the headline sea-level range.
- MSS, *V3 Report for Stakeholders*, Chapter 5: Table 5.10, relative sea-level rise by gauge, scenario and year.
- PUB, *Code of Practice on Coastal Protection*, First Edition (June 2026): the RMSLR planning scenarios, extreme sea level definitions, SHD and Chart Datum.
- PUB COP on Surface Water Drainage: Cl. 2.1.1 and 2.3 (platform and reclamation levels), Cl. 4.11 (sea outfalls), Cl. 10.1 (pumped drainage).
- MPA tide predictions as published on NEA's Tide Timings page (November and December 2026). NCCS on the definition of SHD. MSE, Coastal Protection Bill second reading speech (6 March 2026).
- Chow, Maidment & Mays (1988), *Applied Hydrology*, McGraw-Hill: alternating block method. Chow (1959), *Open-Channel Hydraulics*, McGraw-Hill: standard step method.

## Licence

MIT (code and generated results). The PUB codes of practice, the EPA manual and the V3 reports are third-party documents and are only referenced. The tide predictions are MPA's, as published by NEA, and the table is not redistributed: `data/tide_extract_mpa_2026-11_12.json` holds only summary statistics computed from it and three predicted extremes, with attribution, and is not covered by the MIT licence.
