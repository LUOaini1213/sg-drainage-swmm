# sg-drainage-swmm

**Screening-level surface-water drain design and check, following PUB's Code of Practice on Surface Water Drainage, on a SYNTHETIC catchment.**

> **Read this first.** This is a personal learning project. The catchment, levels and land use are invented. It is not a PUB-approved design, not a submission, and not professional engineering advice. Drain design in Singapore is done and endorsed by a Qualified Person / Professional Engineer under the COP and PUB's requirements. The COP itself is not redistributed here: it is referenced (see [docs/sources.md](docs/sources.md)).

<!-- README.md is generated from docs/README.template.md by scripts/run_all.py. Do not edit README.md by hand. -->

## What it does

1. **Catchment.** A {{inputs_used.catchment.total_area_ha}} ha synthetic residential estate: {{inputs_used.catchment.n_subcatchments}} sub-catchments, {{inputs_used.catchment.n_reaches}} open U-drain reaches ({{inputs_used.catchment.total_drain_length_m}} m) along a road grid, one free outfall. Runoff coefficients are area-weighted from the COP land-use classes (C = {{inputs_used.catchment.c_min|.2f}} to {{inputs_used.catchment.c_max|.2f}}).
2. **Rational-method design** per COP Clause 7: Qr = C I A / {{inputs_used.cop.rational_divisor}}, IDF from COP Appendix 4 (digitised, see below), {{inputs_used.catchment.design_return_period_yr}}-year return period (Clause 7.1.3, catchment under {{inputs_used.cop.return_period_by_area.0.0}} ha), tc = overland time + drain flow time iterated to a fixed point, and the smallest rectangular concrete section that meets Manning capacity with {{inputs_used.cop.freeboard_pct}}% freeboard, {{inputs_used.cop.v_min|.1f}} to {{inputs_used.cop.v_max_concrete|.1f}} m/s and Froude number at most {{inputs_used.cop.froude_max}}.
3. **Hydraulic check in EPA SWMM 5.2** (official engine via `swmm-toolkit`): the same network, dynamic-wave routing, a {{inputs_used.storm.duration_min}}-minute alternating-block design storm built from the same IDF curve.
4. **Stress test:** the design sizes under a climate uplift (both ends of the range published for Singapore's Third National Climate Change Study) and under the {{stress_summary.scenarios.t100.T}}-year storm; which reaches fail, the minimum upsizing that restores COP compliance, and what SWMM says about it.
5. **Drawing-like outputs:** a plan with reach IDs and utilisation colours, and a long-section of the main drain.

## Headline numbers

All values below are generated from files in [`results/`](results/) by `scripts/run_all.py`.

| | |
|---|---|
| Design storm | {{design_summary.return_period_yr}}-year, IDF from COP Appendix 4; alternating-block hyetograph, {{inputs_used.storm.dt_min}}-min blocks, {{inputs_used.storm.design_depth_mm}} mm in {{inputs_used.storm.duration_min}} min, peak block {{inputs_used.storm.design_peak_block_mm_hr}} mm/hr |
| Reaches designed | {{design_summary.n_reaches}}, all meeting the COP checks used: {{design_summary.all_compliant|yesno}}; tc iteration converged for all: {{design_summary.all_converged|yesno}} (at most {{design_summary.max_iterations}} iterations) |
| Max capacity utilisation (Qr / capacity at {{inputs_used.swmm.freeboard_depth_ratio}} D) | {{design_summary.max_utilisation|.3f}} (reach {{design_summary.max_utilisation_reach}}); range {{design_summary.min_utilisation|.3f}} to {{design_summary.max_utilisation|.3f}} |
| Outfall design flow | {{design_summary.outfall_q_m3s}} m3/s at tc = {{design_summary.outfall_tc_min|.1f}} min, I = {{design_summary.outfall_intensity_mm_hr}} mm/hr, section {{design_summary.outfall_section}} |
| SWMM peak / rational Qr | {{swmm_summary.swmm_over_rational_min|.2f}} to {{swmm_summary.swmm_over_rational_max|.2f}} across the reaches (outfall {{swmm_summary.outfall_swmm_peak_m3s}} vs {{swmm_summary.outfall_rational_q_m3s}} m3/s) |
| SWMM, design storm, design sizes | overtopping at {{swmm_summary.design.n_flooded_nodes}} nodes, {{swmm_summary.design.flood_volume_m3|.0f}} m3 in total; water enters the COP freeboard in {{swmm_summary.design.n_reaches_into_freeboard}} of {{design_summary.n_reaches}} reaches |
| SWMM continuity error | design run: runoff {{swmm_summary.runoff_continuity_error_pct}}%, routing {{swmm_summary.routing_continuity_error_pct}}%; largest magnitude over all {{swmm_run_log.n_runs}} SWMM runs: {{swmm_run_log.max_abs_continuity_error_pct}}% (test threshold {{swmm_run_log.threshold_pct}}%) |
| Headroom of the design sizes | the first reach breaks a COP criterion at +{{stress_summary.min_first_failure_uplift_pct}}% intensity, the last at +{{stress_summary.max_first_failure_uplift_pct}}% |
| {{stress_summary.scenarios.t100.T}}-year storm | {{stress_summary.scenarios.t100.n_rational_failing}} of {{design_summary.n_reaches}} reaches fail (max utilisation {{stress_summary.scenarios.t100.max_utilisation_existing|.2f}}); SWMM overtopping {{stress_summary.scenarios.t100.swmm_existing.flood_volume_m3|.0f}} m3; minimum rational upsizing: {{stress_summary.scenarios.t100.n_upsized}} reaches, +{{stress_summary.scenarios.t100.drain_volume_increase_pct}}% drain volume |
| {{stress_summary.scenarios.cc_v3_high.T}}-year +{{stress_summary.scenarios.cc_v3_high.uplift_pct}}% (bounding climate case) | {{stress_summary.scenarios.cc_v3_high.n_rational_failing}} of {{design_summary.n_reaches}} reaches fail (max utilisation {{stress_summary.scenarios.cc_v3_high.max_utilisation_existing|.2f}}); SWMM overtopping {{stress_summary.scenarios.cc_v3_high.swmm_existing.flood_volume_m3|.0f}} m3; minimum rational upsizing: +{{stress_summary.scenarios.cc_v3_high.drain_volume_increase_pct}}% drain volume |

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

## Design table (rational method, {{design_summary.return_period_yr}}-year)

{{table:design}}

`Util.` = Qr / Qc, where Qc is Manning capacity with the water surface at {{inputs_used.swmm.freeboard_depth_ratio}} D, i.e. keeping the COP freeboard. Sub-catchment runoff enters at the upstream node of the reach it drains to. All invert gradients follow the ground (gradient changes needed: {{design_summary.n_gradient_changed}}). Full columns, including the convergence residual of the tc iteration, are in [`results/design_table.csv`](results/design_table.csv). Invert and cope levels are in [`results/design_levels.csv`](results/design_levels.csv).

![Plan](results/figures/plan_utilisation.png)

![Long-section](results/figures/long_section_main.png)

Design sensitivity ([`results/sensitivity_design.json`](results/sensitivity_design.json)):

- Overland time is the COP's widest open choice (Clause 7.1.4 allows {{inputs_used.cop.overland_time_min_range.0}} to {{inputs_used.cop.overland_time_min_range.1}} min). Setting it to the bottom of that range for every sub-catchment raises the outfall flow by {{sensitivity_design.overland_5min.outfall_q_change_pct}}% and changes {{sensitivity_design.overland_5min.n_size_changes}} of {{design_summary.n_reaches}} sections. Setting it to the top of the range changes the outfall flow by {{sensitivity_design.overland_15min.outfall_q_change_pct}}% and changes {{sensitivity_design.overland_15min.n_size_changes}} sections.
- The IDF digitisation has a one-pixel reading resolution of about {{inputs_used.idf_digitisation.one_pixel_reading_uncertainty_pct}}% in intensity. Shifting all intensities by minus or plus one percent changes {{sensitivity_design.idf_minus1pct.n_size_changes}} and {{sensitivity_design.idf_plus1pct.n_size_changes}} sections respectively.

## SWMM check

{{table:swmm}}

SWMM peaks are higher than the rational Qr in every reach (ratio {{swmm_summary.swmm_over_rational_min|.2f}} to {{swmm_summary.swmm_over_rational_max|.2f}}). The difference is expected, and most of it can be traced at sub-catchment level ([`results/subcatchment_swmm_vs_rational.csv`](results/subcatchment_swmm_vs_rational.csv)):

{{table:subcatchments}}

- **Duration factor** = peak {{inputs_used.storm.dt_min}}-minute block intensity / IDF intensity at the overland time used in the rational method. The rational method applies the intensity for a duration equal to tc, with a {{inputs_used.cop.overland_time_min_range.0}} to {{inputs_used.cop.overland_time_min_range.1}} min overland time. SWMM's surface runoff from short, smooth paved areas responds within minutes, so it picks up the {{inputs_used.storm.dt_min}}-minute peak that the alternating-block storm contains. Range: {{swmm_summary.sub_duration_factor_min|.2f}} to {{swmm_summary.sub_duration_factor_max|.2f}}.
- **Runoff factor** = (SWMM peak runoff / peak rainfall rate on the area) / COP C. SWMM's losses (depression storage plus Green-Ampt infiltration in a clay-loam soil) remove less water at the peak than the COP coefficients imply. Range: {{swmm_summary.sub_runoff_factor_min|.2f}} to {{swmm_summary.sub_runoff_factor_max|.2f}}. Event runoff coefficients in SWMM are {{swmm_summary.sub_event_runoff_coeff_min}} to {{swmm_summary.sub_event_runoff_coeff_max}}, against COP C of {{inputs_used.catchment.c_min|.2f}} to {{inputs_used.catchment.c_max|.2f}}.
- In the network, routing through the drains attenuates and offsets the sub-catchment peaks, which fits the reach ratios lying between the sub-catchment extremes. Where a drain runs full, SWMM also caps the flow: `SWMM max y/D` reaches the full drain depth, and the excess overtops at the upstream node.
- SWMM's peak velocity also exceeds the COP's {{inputs_used.cop.v_max_concrete|.1f}} m/s limit in reach(es) {{swmm_summary.design.reaches_over_vmax|list}}. The rational check at normal depth does not show this.
- A sandier soil (sandy loam, SWMM manual Table A.2) lowers the event runoff coefficient to {{swmm_summary.sandy_loam.event_runoff_coefficient}} but barely moves the outfall peak ({{swmm_summary.sandy_loam.outfall_swmm_peak_m3s}} m3/s). Overtopping falls to {{swmm_summary.sandy_loam.flood_volume_m3|.0f}} m3. Losses matter less than timing for these peaks.

**SWMM-led upsizing (heuristic).** Repeatedly enlarging the most downstream failing reaches by one catalogue step, until SWMM shows no overtopping and no reach deeper than {{inputs_used.swmm.freeboard_depth_ratio}} D, takes {{swmm_summary.greedy_upsizing_design_storm.n_changed}} reaches and +{{swmm_summary.greedy_upsizing_design_storm.drain_volume_increase_pct}}% drain volume for the design storm. The heuristic only targets depth: its final peak velocity is {{swmm_summary.greedy_upsizing_design_storm.final_max_velocity_ms|.2f}} m/s against the COP limit of {{inputs_used.cop.v_max_concrete|.1f}} m/s. It is not proven minimal.

![SWMM vs rational](results/figures/swmm_vs_rational.png)

Continuity: runoff {{swmm_summary.runoff_continuity_error_pct}}% and flow routing {{swmm_summary.routing_continuity_error_pct}}% for the design run. Across all {{swmm_run_log.n_runs}} SWMM runs the largest magnitude is {{swmm_run_log.max_abs_continuity_error_pct}}% ([`results/swmm_run_log.json`](results/swmm_run_log.json)). The tests require below {{swmm_run_log.threshold_pct}}%.

## Stress test

Uplifts are applied multiplicatively to the {{design_summary.return_period_yr}}-year IDF intensities. The +{{stress_summary.scenarios.cc_v3_low.uplift_pct}}% and +{{stress_summary.scenarios.cc_v3_high.uplift_pct}}% values are the two ends of the range the V3 news release gives for extreme *daily* rainfall in April and May. Applying a daily-rainfall change to short-duration intensities is this project's assumption. The upper end is treated as a bounding case, not a projection for design. The {{stress_summary.scenarios.t100.T}}-year case uses the COP's own {{stress_summary.scenarios.t100.T}}-year curve.

{{table:stress}}

"Minimum rational upsizing" keeps each reach's gradient and never shrinks a section. It picks the smallest catalogue section that passes every COP check again, and is minimal within the catalogue by construction. Because SWMM peaks run above rational Qr, those sections still overtop in SWMM. The SWMM-led column shows the larger enlargement the dynamic check asks for.

{{table:upsizing}}

Uplift sweep with the design sizes, in {{inputs_used.sweep.rational_step_pct}}% steps for the rational check and {{inputs_used.sweep.swmm_step_pct}}% steps in SWMM ([`results/uplift_sweep_rational.csv`](results/uplift_sweep_rational.csv), [`results/uplift_sweep_swmm.csv`](results/uplift_sweep_swmm.csv)):

{{table:first_failure}}

![Uplift sweep](results/figures/uplift_sweep.png)

The design sizes have almost no headroom. Smallest-compliant sizing plus a {{inputs_used.catalogue.step_m}} m size grid leaves utilisations of {{design_summary.min_utilisation|.3f}} to {{design_summary.max_utilisation|.3f}}, so any uplift breaks some reach. A real design would choose standard sections, usually with margin.

## Method

- **Rational formula** (COP Cl. 7.1.1): Qr = C I A / {{inputs_used.cop.rational_divisor}} (m3/s, mm/hr, ha). C is weighted by area from the Cl. 7.1.2 classes: roads/paved {{inputs_used.cop.runoff_c.road|.2f}}, urban {{inputs_used.cop.runoff_c.urban|.2f}}, vegetated/pervious {{inputs_used.cop.runoff_c.vegetated|.2f}}.
- **Return period** (Cl. 7.1.3): {{design_summary.return_period_yr}} years for a catchment under {{inputs_used.cop.return_period_by_area.0.0}} ha.
- **IDF**: the COP gives the IDF relationship only as a chart (Appendix 4). `tools/digitize_idf.py` reads the embedded chart image, calibrates both log axes from the detected grid lines, and traces all eight return-period curves. It tabulates {{inputs_used.idf_digitisation.n_durations}} durations from {{inputs_used.idf_digitisation.duration_min}} to {{inputs_used.idf_digitisation.duration_max}} min. Reading resolution is about {{inputs_used.idf_digitisation.one_pixel_reading_uncertainty_pct}}% per pixel, and the largest local-fit residual is {{inputs_used.idf_digitisation.max_local_fit_residual_px}} px. Between tabulated durations, values are interpolated linearly on log-log axes.
- **Time of concentration** (Cl. 7.1.4): tc = to + td. The overland time to is taken per land use within the COP's {{inputs_used.cop.overland_time_min_range.0}} to {{inputs_used.cop.overland_time_min_range.1}} min range ({{inputs_used.catchment.overland_time_values_min|list}} min). The drain time td comes from the Manning velocity in the chosen section. Because the section depends on Qr, which depends on tc, each reach is iterated to a fixed point (tolerance in `sgdrain/rational.py`).
- **Sizing** (Cl. 7.2.2, 7.2.3, 7.3.1 to 7.3.4, 4.3.1): rectangular open concrete drain, n = {{inputs_used.cop.manning_n_concrete}}, steady uniform flow at normal depth. A section is accepted if y is at most {{inputs_used.swmm.freeboard_depth_ratio}} D, V is between {{inputs_used.cop.v_min|.1f}} and {{inputs_used.cop.v_max_concrete|.1f}} m/s, and Fr is at most {{inputs_used.cop.froude_max}}. Width and depth must each be at least {{inputs_used.cop.min_drain_dimension_mm}} mm, and sections come from a {{inputs_used.catalogue.step_m}} m catalogue ({{inputs_used.catalogue.width_min_m}} to {{inputs_used.catalogue.width_max_m}} m wide, {{inputs_used.catalogue.depth_min_m}} to {{inputs_used.catalogue.depth_max_m}} m deep). The smallest area wins. The invert follows the ground slope; a list of alternative gradients is tried only if no section fits.
- **Levels**: the drain cope is at or below ground at both ends, and no drain starts above the inverts of the drains flowing into it.
- **Hyetograph**: alternating block (Chow, Maidment & Mays, *Applied Hydrology*, 1988, ch. 14), {{inputs_used.storm.dt_min}}-min blocks over {{inputs_used.storm.duration_min}} min with the peak in the centre. The central window of k blocks holds the k largest IDF depth increments. The storm therefore reaches at least the IDF depth for every duration up to its length, and exactly that depth where the digitised depth-duration curve is concave. A test checks this.
- **SWMM**: SWMM 5.2 through `swmm-toolkit`, dynamic wave, {{inputs_used.swmm.options.routing_step_s}} s routing step. Conduits are open rectangular, invert elevations come from the design, and the outfall is free. Node overflow level is the highest drain cope at the node, with no ponding: water above it is reported as overtopping (flooding) and lost. Sub-catchment parameters are in [Assumptions](#assumptions).

## Assumptions

- **Synthetic catchment**: geometry, ground levels (arbitrary local datum, not SHD), land-use split and overland times are invented to look plausible. No public elevation data was used.
- **Lumped inflow**: each sub-catchment discharges at the upstream node of its reach. This is conservative for the rational method and identical in SWMM.
- **Minimum size**: COP Cl. 4.3.1 sets the {{inputs_used.cop.min_drain_dimension_mm}} mm minimum for roadside drains in a *closed* drainage system. It is applied here to every drain.
- **Size catalogue and gradient list**: illustrative. Real roadside drains follow the LTA standard details referenced in COP Cl. 9.1.2 / Drawing No. 1, which were not used.
- **SWMM hydrology** (sources in [docs/sources.md](docs/sources.md)): percent impervious = roads {{inputs_used.swmm.impervious_pct.road}}%, urban plots {{inputs_used.swmm.impervious_pct.urban}}%, vegetated {{inputs_used.swmm.impervious_pct.vegetated}}%. Overland flow length is {{inputs_used.catchment.overland_length_min_m}} to {{inputs_used.catchment.overland_length_max_m}} m depending on land use, and width = area / length. N-imperv {{inputs_used.swmm.hydrology.n_imperv}}, N-perv {{inputs_used.swmm.hydrology.n_perv}} (SWMM manual Table A.6). Depression storage {{inputs_used.swmm.hydrology.dstore_imperv_mm}} / {{inputs_used.swmm.hydrology.dstore_perv_mm}} mm (lower end of Table A.5). %Zero-Imperv {{inputs_used.swmm.hydrology.pct_zero_imperv}}. Green-Ampt clay loam from Table A.2: suction {{inputs_used.swmm.hydrology.ga_suction_mm}} mm, Ksat {{inputs_used.swmm.hydrology.ga_ksat_mm_hr}} mm/hr, initial deficit {{inputs_used.swmm.hydrology.ga_initial_deficit}}. None of this is calibrated.
- **Climate uplift**: one multiplier on every duration, taken from the range given for extreme *daily* rainfall (see Stress test).

## Limitations

- Screening only: no structural, geotechnical, utility, maintenance-access or construction checks. No sumps, transitions or bends (COP Cl. 9), no dry-weather-flow channel detail (Cl. 7.3.1, Drawing No. 1), no culverts. Outfall tailwater and tidal or canal levels are ignored (free outfall).
- Cl. 7.1.5 (maximum allowable peak runoff from larger development sites, usually met with on-site detention) is outside this exercise.
- The IDF values are a digitisation of a scanned chart, not PUB tabulated data.
- The rational method's checks are at normal depth. Backwater only appears in SWMM.
- SWMM overland-flow and loss parameters are textbook values, not calibrated to any Singapore catchment. The SWMM/rational gap depends on them and on the choice of an alternating-block storm, which nests every duration's peak in one event.
- The SWMM-led upsizing is a greedy heuristic and only looks at depth and overtopping.

## Repository layout

```
data/        synthetic catchment definition, digitised IDF table and its metadata
sgdrain/     COP constants (cop.py), Manning (hydraulics.py), IDF, hyetograph,
             rational design/check/upsize, SWMM writer/runner, pipeline, plots, README renderer
scripts/     run_all.py - regenerates results/ and README.md
results/     every number quoted above (CSV/JSON), figures, SWMM .inp models
tools/       digitize_idf.py - IDF chart digitiser (needs a local copy of the COP PDF)
tests/       pytest suite (offline)
mutation/    mutation testing of the test suite and its report
docs/        README template and sources with clause references
```

## Tests

`pytest` runs {{mutation_report.baseline_passed}} tests offline. They cover:

- Manning and continuity invariants: capacity monotonic in width, depth and slope, Q = V A, and normal depth as the inverse of Manning.
- Rational-method arithmetic.
- Weighted C and the COP return-period rule.
- tc convergence, with each residual re-checked independently.
- Smallest-section optimality and COP criteria on every reach.
- The alternating-block window property.
- SWMM continuity below {{swmm_run_log.threshold_pct}}%, and a re-run of the SWMM design model checked against the committed results.
- Upsizing never shrinks a section and restores compliance.
- README numbers checked against `results/`.

**Mutation test of the tests** ([`mutation/run_mutants.py`](mutation/run_mutants.py), report in [`results/mutation_report.json`](results/mutation_report.json)). The script plants {{mutation_report.n_mutants}} deliberate bugs, one at a time, in a scratch copy of the repo. It first checks that the unmodified suite passes and that every mutant compiles. The suite killed **{{mutation_report.n_killed}} of {{mutation_report.n_mutants}}** mutants. Survivors: {{mutation_report.survivors|list}}.

## Sources

Full list with URLs, retrieval dates and clause/table/page references: [docs/sources.md](docs/sources.md). In short:

- PUB, *Code of Practice on Surface Water Drainage*, Seventh Edition (Dec 2018) with amendments under Addendum No. 3 (April 2025). Clauses 4.3.1, 7.1.1 to 7.1.4, 7.2.2, 7.2.3, 7.3.1 to 7.3.4 and Appendix 4.
- US EPA, *Storm Water Management Model User's Manual Version 5.2* (EPA/600/R-22/030, 2022): Tables A.2, A.5 and A.6.
- MSS/MSE joint news release on Singapore's Third National Climate Change Study (V3), 5 January 2024: the range for extreme daily rainfall.
- Chow, Maidment & Mays (1988), *Applied Hydrology*, McGraw-Hill: alternating block method.

## Licence

MIT (code and generated results). The PUB COP and the EPA manual are third-party documents and are only referenced.
