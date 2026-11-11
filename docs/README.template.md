# sg-drainage-swmm

**Screening-level surface-water drain design and check, following PUB's Code of Practice on Surface Water Drainage, on a SYNTHETIC catchment.**

> **Read this first.** This is a personal learning project. The catchment, levels and land use are invented. It is not a PUB-approved design, not a submission, and not professional engineering advice. Drain design in Singapore is done and endorsed by a Qualified Person / Professional Engineer under the COP and PUB's requirements. The COP itself is not redistributed here: it is referenced (see [docs/sources.md](docs/sources.md)).

<!-- README.md is generated from docs/README.template.md by scripts/run_all.py. Do not edit README.md by hand. -->

## What it does

1. **Catchment.** A {{inputs_used.catchment.total_area_ha}} ha synthetic residential estate: {{inputs_used.catchment.n_subcatchments}} sub-catchments, {{inputs_used.catchment.n_reaches}} open U-drain reaches ({{inputs_used.catchment.total_drain_length_m}} m) along a road grid, one outfall. Runoff coefficients are area-weighted from the COP land-use classes (C = {{inputs_used.catchment.c_min|.2f}} to {{inputs_used.catchment.c_max|.2f}}).
2. **Rational-method design** per COP Clause 7: Qr = C I A / {{inputs_used.cop.rational_divisor}}, IDF from COP Appendix 4 (digitised, see below), {{inputs_used.catchment.design_return_period_yr}}-year return period (Clause 7.1.3, catchment under {{inputs_used.cop.return_period_by_area.0.0}} ha), tc = overland time + drain flow time iterated to a fixed point, and the smallest rectangular concrete section that meets Manning capacity with {{inputs_used.cop.freeboard_pct}}% freeboard, {{inputs_used.cop.v_min|.1f}} to {{inputs_used.cop.v_max_concrete|.1f}} m/s and Froude number at most {{inputs_used.cop.froude_max}}.
3. **Hydraulic check in EPA SWMM 5.2** (official engine via `swmm-toolkit`): the same network, dynamic-wave routing, a {{inputs_used.storm.duration_min}}-minute alternating-block design storm built from the same IDF curve.
4. **Stress test:** the design sizes under a climate uplift (both ends of the range published for Singapore's Third National Climate Change Study) and under the {{stress_summary.scenarios.t100.T}}-year storm; which reaches fail, the minimum upsizing that restores COP compliance, and what SWMM says about it.
5. **Drawing-like outputs:** a plan with reach IDs and utilisation colours, and a long-section of the main drain.
6. **Tide and sea-level rise at the outfall:** the free outfall is replaced by the published tide (MPA predictions) raised by official sea-level-rise figures (Third National Climate Change Study, PUB Code of Practice on Coastal Protection), for the design storm and every stress storm. It reports which reaches lose the COP freeboard, how far the backwater reaches, and screening-level responses: outfall level, drain upsizing, flap gate, pump and sump. See [Tide and sea-level rise](#tide-and-sea-level-rise-at-the-outfall).

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
| Tide and sea-level rise, outfall ground at {{tide_inputs.datum.outfall_ground_shd|.1f}} m SHD (assumption) | today's highest predicted high water ({{tide_inputs.datum.hw_now_shd|.2f}} m SHD) plus up to {{tide_inputs.coastal.cpcop_rmslr_planning_scenarios_m.1}} m of rise stays below the level that costs freeboard: no reach loses the COP freeboard and SWMM overtopping changes by {{tide_summary.base_design.cpcop_2p15.open.d_flood_m3|.0f}} m3 |
| Highest outfall water level that keeps the COP freeboard | {{tide_summary.design_tw_crit_shd|.2f}} m SHD, {{tide_summary.design_tw_crit_below_ground_m|.2f}} m below the outfall ground; {{tide_summary.design_slr_headroom_m|.2f}} m above today's highest predicted high water |
| Sea at the outfall ground (sweep) | {{tide_summary.sweep_at_ground.gvf_n_fail_due_to_tide}} reaches lose the freeboard, backwater {{tide_summary.sweep_at_ground.gvf_extent_main_m|.0f}} m up the main drain, SWMM +{{tide_summary.sweep_at_ground.d_flood_m3_open|.0f}} m3; no drain upsizing restores the freeboard; a pump of {{tide_summary.pump.storms.design_10yr_design.verification.pump_m3s|.2f}} m3/s with a {{tide_summary.pump.storms.design_10yr_design.verification.storage_m3|.0f}} m3 sump behind a shut gate brings SWMM back to the free-outfall result |

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

## Tide and sea-level rise at the outfall

Everything above assumes a free outfall. Here the water level at the outfall follows the sea. Numbers come from [`results/tide_summary.json`](results/tide_summary.json), [`results/tide_scenarios.csv`](results/tide_scenarios.csv), [`results/tide_datum_sensitivity.csv`](results/tide_datum_sensitivity.csv), [`results/tide_level_sweep.csv`](results/tide_level_sweep.csv) and [`results/tide_inputs.json`](results/tide_inputs.json); sources with clause and page numbers are in [docs/sources.md](docs/sources.md).

**Sea level at the outfall.**

- **Tide:** MPA's predicted high and low waters for November and December 2026, as published on NEA's Tide Timings page: {{tide_inputs.tide.n_extremes}} values in metres above Chart Datum. The page does not name the station. The table itself is not in this repository, because NEA's website terms do not allow redistribution; [`data/tide_extract_mpa_2026-11_12.json`](data/tide_extract_mpa_2026-11_12.json) holds the statistics quoted here and the three predicted extremes around the highest high water, which are all the runs use. The highest predicted high water is {{tide_inputs.tide.highest_hw_cd}} m CD (first on {{tide_inputs.tide.hw_used_time_text}}, Singapore time assumed). The time-mean of the predicted curve is {{tide_inputs.tide.mean_level_cd}} m CD, so that high water stands {{tide_inputs.tide.hw_above_mean_m}} m above the mean (the average predicted high water stands {{tide_inputs.tide.mean_hw_above_mean_m}} m above it). Between predicted extremes the level follows a half cosine. SWMM gets the predicted curve around that high water as a TIMESERIES outfall, with high water at the centre of the storm's peak {{inputs_used.storm.dt_min}}-minute block, i.e. storm peak and spring high water coincide.
- **Sea-level rise**, added to the whole curve, one official figure per scenario, no interpolation: {{tide_inputs.coastal.slr_scenarios.1.label}}, {{tide_inputs.coastal.slr_scenarios.2.label}}, {{tide_inputs.coastal.slr_scenarios.3.label}}. The CPCOP gives no year for its two planning scenarios. The V3 figure is the top of the likely range at Sultan Shoal, the gauge with the highest projections (V3 Report for Stakeholders, Table 5.10, relative to {{tide_inputs.coastal.v3_baseline}}). The same table gives a Singapore average (median of six gauges) of {{tide_inputs.coastal.v3_ssp585_2100_singapore_average_m}} m for SSP5-8.5 by 2100, and {{tide_inputs.coastal.v3_ssp585_2150_sultan_shoal_likely_high_m}} m as the top of the SSP5-8.5 likely range at Sultan Shoal by 2150.
- **Outfall:** open (the tide enters the drains, which start filled to the tide level) or with a flap gate (the drains start empty and discharge only when they stand above the sea).
- **Not included:** storm surge and waves. PUB's extreme sea levels for the CPCOP, which add surge, are still under review (CPCOP Cl. 4.3, footnote). Official statements put the combined level at up to {{tide_inputs.coastal.combined_extreme_above_msl_m}} m above today's mean sea level with storm surge and high tide (MSE, 2026). Under assumptions A1 and A2 that is above the ground at {{tide_inputs.datum.n_nodes_ground_below_combined_extreme}} of the {{tide_inputs.datum.n_nodes}} nodes of this catchment: a coastal protection question, not a drain one.

**Datum. ASSUMPTIONS, needed because the catchment is synthetic.**

- **A1:** the ground at the outfall node is at {{tide_inputs.datum.outfall_ground_shd|.1f}} m SHD, the COP minimum platform level for developments along the southern coast (Cl. 2.1.1(a)(i); also the minimum reclamation level, Cl. 2.3). The local datum is then SHD + {{tide_inputs.datum.local_minus_shd_m}} m: the outfall invert sits at {{tide_inputs.datum.outfall_invert_shd|.2f}} m SHD and the ground runs from {{tide_inputs.datum.ground_min_shd|.2f}} to {{tide_inputs.datum.ground_max_shd|.2f}} m SHD.
- **A2:** the time-mean of the predicted tide is taken as {{tide_inputs.coastal.tide_mean_shd|.1f}} m SHD. SHD is based on the mean sea level at Victoria Dock in 1935-1937 (NCCS). The official Chart Datum to SHD conversion is held by MPA's Hydrographic Division (CPCOP terminology) and was not available. The predictions also cover only two months of the north-east monsoon, so their mean need not be the annual mean.
- Hydraulically only the sea level relative to the drains matters, so both assumptions act through one number: high water minus outfall ground. Lowering the assumed outfall ground by some amount is the same as raising the tide datum, or the sea, by that amount. The sensitivity runs move the outfall ground from {{tide_inputs.coastal.outfall_ground_shd_sensitivity.0}} to {{tide_inputs.coastal.outfall_ground_shd_sensitivity.4}} m SHD, and a sweep moves high water from {{tide_inputs.settings.sweep_min}} to {{tide_inputs.settings.sweep_max}} m relative to the outfall ground.

**Two checks.** SWMM runs each storm against each sea level and compares with the same storm and drains on a free outfall: extra overtopping, newly flooded nodes, and the rise of each node's maximum water level (a node counts as raised at {{tide_inputs.settings.swmm_rise_tol_m}} m or more; at a node that already overtops, the level is capped at the cope, so extra overtopping shows in volume, not level). The steady check computes backwater curves (standard step, {{tide_inputs.settings.gvf_dx_m}} m stations) at the rational design flows with the outfall held at the high-water level, and applies the COP freeboard (Cl. 7.3.4) along every reach. It reports the reaches that lose the freeboard because of the sea, and how far up the main drain the level rises by {{tide_inputs.settings.gvf_rise_tol_m}} m or more over the free-outfall profile.

### Results at the base assumption

{{table:tide_base}}

At the base assumption the sea changes nothing for the design storm. Today's highest predicted high water stands {{tide_summary.base_design.present.open.peak_above_outfall_invert_m|abs}} m below the outfall invert. With {{tide_inputs.coastal.cpcop_rmslr_planning_scenarios_m.1}} m of rise it stands {{tide_summary.base_design.cpcop_2p15.open.peak_above_outfall_invert_m}} m above the invert and reaches into the lower ends of reaches {{tide_summary.base_design.cpcop_2p15.open.reaches_below_high_water|list}}, but stays below the water level the design flow itself needs at the outfall. No reach loses the freeboard and no node's maximum level rises. Across all {{tide_summary.base_n_runs}} storm, drain-size, sea-level and gate combinations at the base assumption, the largest change in SWMM overtopping is {{tide_summary.base_largest_d_flood.d_flood_m3|.0f}} m3 ({{tide_summary.base_largest_d_flood.storm_label}}, {{tide_summary.base_largest_d_flood.sizes}}, largest node rise {{tide_summary.base_largest_d_flood.max_head_rise_m}} m):

{{table:tide_storms}}

Upsizing for heavier rain lowers the level the outfall can tolerate. The +{{stress_summary.scenarios.cc_v3_high.uplift_pct}}% upsizing deepens the outfall drain to {{tide_summary.critical_tailwater_by_tag.cc_v3_high_upsized.outfall_section}} m, so its invert sits lower and its {{inputs_used.cop.freeboard_pct}}% freeboard is larger. Its highest tolerable outfall level is {{tide_summary.critical_tailwater_by_tag.cc_v3_high_upsized.tw_crit_shd}} m SHD, against {{tide_summary.critical_tailwater_by_tag.design_10yr_design.tw_crit_shd}} m SHD for the design sizes.

![Long-section with tide and sea-level rise](results/figures/long_section_tide.png)

### Where the sea starts to matter

The datum sensitivity (design storm, design sizes; each cell is the open-outfall run):

{{table:tide_datum}}

The effect is a threshold. Nothing happens while high water stays below the water level the design flow itself needs at the outfall. The {{tide_inputs.datum.outfall_drain_depth_m}} m deep outfall drain runs at normal depth just under its freeboard line, so the COP freeboard is gone as soon as the sea passes {{tide_summary.design_tw_crit_below_ground_m}} m below the outfall cope, and the land floods from the sea once it passes the ground. The sweep shows where this happens: every sweep level at which anything changed is listed below (all lower levels change nothing).

{{table:tide_sweep}}

![Sweep of the high-water level](results/figures/tide_level_sweep.png)

**How far upstream the backwater reaches.** At the base assumption, nowhere: the longest steady backwater over all base runs is {{tide_summary.base_max_gvf_extent_m|.0f}} m, and the largest rise of any node's maximum level in SWMM is {{tide_summary.base_max_head_rise_m}} m. In the sweep the steady backwater first appears when high water comes within {{tide_summary.sweep_first_gvf_rise_hw_minus_ground_m|abs}} m of the outfall ground. With the sea at the outfall ground it runs {{tide_summary.sweep_at_ground.gvf_extent_main_m|.0f}} m up the main drain and raises reaches {{tide_summary.sweep_at_ground.gvf_raised_reaches|list}}; reaches {{tide_summary.sweep_at_ground.gvf_fail_due_to_tide|list}} lose the COP freeboard. In SWMM the nodes raised by {{tide_inputs.settings.swmm_rise_tol_m}} m or more are {{tide_summary.sweep_at_ground.raised_nodes_open|list}}, by up to {{tide_summary.sweep_at_ground.max_head_rise_m_open}} m. The largest difference in overtopping between open and flap-gated runs anywhere in the sweep is {{tide_summary.sweep_max_open_gated_diff_m3|.0f}} m3: a flap gate keeps seawater out of the drains before the storm, but does not help them discharge against a high sea.

### Screening-level responses

These are screening estimates on a synthetic catchment, not designs.

1. **Outfall level.** With the design sizes the outfall water level must stay at or below {{tide_summary.design_tw_crit_shd}} m SHD ({{tide_summary.design_tw_crit_below_ground_m}} m below the outfall ground) to keep the COP freeboard at the design flow. Put the other way, the lowest outfall ground that keeps a gravity outfall working for each sea level is:

{{table:tide_min_ground}}

   With the outfall ground at the COP minimum platform level, the margin over the {{tide_inputs.coastal.cpcop_rmslr_planning_scenarios_m.1}} m planning scenario's predicted high water is {{tide_summary.min_outfall_ground.3.margin_at_cop_platform_level_m}} m, before any storm surge.
2. **Drain upsizing under tailwater: does not work here.** The search tries every larger catalogue section (width and depth never reduced, gradient kept, normal-depth COP checks still met), reach by reach from the outfall up. At every sweep level that costs freeboard it finds none (last column of the sweep table). The sea fixes the water level at the outfall. A wider drain only flattens the water surface further up. A deeper drain keeps its cope at the ground, so its invert drops and its {{inputs_used.cop.freeboard_pct}}% freeboard grows while the free height above the sea does not.
3. **Flap gate.** Keeps the sea out of the drains between storms, but on its own it changes nothing at the storm peak (above).
4. **Pump and sump behind a shut gate.** When the sea stands above the outfall level the drains can tolerate, everything that reaches the outfall has to be pumped or stored. For a steady rational check a pump of at least the outfall design flow, {{tide_summary.pump.rational_outfall_q_m3s}} m3/s, holds the outfall at the free-outfall level. For the SWMM storms, the storage a sump needs for a given pump comes from the mass curve of the free-outfall inflow (gate shut for the whole storm, drain storage ignored):

{{table:tide_pump}}

   For scale only, COP Cl. 10.1(a), written for pumped drainage of underground facilities and not for estate outfalls, would ask {{tide_summary.pump.cop_cl_10_1_reference_m3s}} m3/s for this {{inputs_used.catchment.total_area_ha}} ha catchment. SWMM check, design storm, sea held at the outfall ground behind a shut flap gate: with no pump, overtopping rises by {{tide_summary.pump.storms.design_10yr_design.verification.gate_shut_no_pump.d_flood_m3|.0f}} m3. With a pump of {{tide_summary.pump.storms.design_10yr_design.verification.pump_m3s}} m3/s ({{tide_inputs.settings.verify_pump_fraction|pct}}% of peak inflow) and a {{tide_summary.pump.storms.design_10yr_design.verification.storage_m3|.0f}} m3 sump ({{tide_summary.pump.storms.design_10yr_design.verification.sump_area_m2|.0f}} m2 over {{tide_summary.pump.storms.design_10yr_design.verification.sump_depth_m}} m), it changes by {{tide_summary.pump.storms.design_10yr_design.verification.gate_shut_pumped.d_flood_m3|.0f}} m3 and no node's maximum level rises by more than {{tide_summary.pump.storms.design_10yr_design.verification.gate_shut_pumped.max_head_rise_m}} m: the free-outfall result is restored. Pump head, start-up and standby pumps are not modelled.

**Joint probability.** Every run puts the storm peak on the highest predicted high water of the two months. The COP does not specify a tailwater for drain design, and the CPCOP's extreme sea levels, which would carry the joint probability of surge and tide, are not yet published. A design storm arriving exactly at the year's highest spring tide is much rarer than the storm alone, so for the tide itself the pairing is conservative. Storm surge, which would raise the sea, is left out, and the V3 rise is counted from its {{tide_inputs.coastal.v3_baseline}} baseline on top of 2026 predictions, which double-counts the rise since then. These runs locate the threshold. They do not say how often it is crossed.

## Method

- **Rational formula** (COP Cl. 7.1.1): Qr = C I A / {{inputs_used.cop.rational_divisor}} (m3/s, mm/hr, ha). C is weighted by area from the Cl. 7.1.2 classes: roads/paved {{inputs_used.cop.runoff_c.road|.2f}}, urban {{inputs_used.cop.runoff_c.urban|.2f}}, vegetated/pervious {{inputs_used.cop.runoff_c.vegetated|.2f}}.
- **Return period** (Cl. 7.1.3): {{design_summary.return_period_yr}} years for a catchment under {{inputs_used.cop.return_period_by_area.0.0}} ha.
- **IDF**: the COP gives the IDF relationship only as a chart (Appendix 4). `tools/digitize_idf.py` reads the embedded chart image, calibrates both log axes from the detected grid lines, and traces all eight return-period curves. It tabulates {{inputs_used.idf_digitisation.n_durations}} durations from {{inputs_used.idf_digitisation.duration_min}} to {{inputs_used.idf_digitisation.duration_max}} min. Reading resolution is about {{inputs_used.idf_digitisation.one_pixel_reading_uncertainty_pct}}% per pixel, and the largest local-fit residual is {{inputs_used.idf_digitisation.max_local_fit_residual_px}} px. Between tabulated durations, values are interpolated linearly on log-log axes.
- **Time of concentration** (Cl. 7.1.4): tc = to + td. The overland time to is taken per land use within the COP's {{inputs_used.cop.overland_time_min_range.0}} to {{inputs_used.cop.overland_time_min_range.1}} min range ({{inputs_used.catchment.overland_time_values_min|list}} min). The drain time td comes from the Manning velocity in the chosen section. Because the section depends on Qr, which depends on tc, each reach is iterated to a fixed point (tolerance in `sgdrain/rational.py`).
- **Sizing** (Cl. 7.2.2, 7.2.3, 7.3.1 to 7.3.4, 4.3.1): rectangular open concrete drain, n = {{inputs_used.cop.manning_n_concrete}}, steady uniform flow at normal depth. A section is accepted if y is at most {{inputs_used.swmm.freeboard_depth_ratio}} D, V is between {{inputs_used.cop.v_min|.1f}} and {{inputs_used.cop.v_max_concrete|.1f}} m/s, and Fr is at most {{inputs_used.cop.froude_max}}. Width and depth must each be at least {{inputs_used.cop.min_drain_dimension_mm}} mm, and sections come from a {{inputs_used.catalogue.step_m}} m catalogue ({{inputs_used.catalogue.width_min_m}} to {{inputs_used.catalogue.width_max_m}} m wide, {{inputs_used.catalogue.depth_min_m}} to {{inputs_used.catalogue.depth_max_m}} m deep). The smallest area wins. The invert follows the ground slope; a list of alternative gradients is tried only if no section fits.
- **Levels**: the drain cope is at or below ground at both ends, and no drain starts above the inverts of the drains flowing into it.
- **Hyetograph**: alternating block (Chow, Maidment & Mays, *Applied Hydrology*, 1988, ch. 14), {{inputs_used.storm.dt_min}}-min blocks over {{inputs_used.storm.duration_min}} min with the peak in the centre. The central window of k blocks holds the k largest IDF depth increments. The storm therefore reaches at least the IDF depth for every duration up to its length, and exactly that depth where the digitised depth-duration curve is concave. A test checks this.
- **SWMM**: SWMM 5.2 through `swmm-toolkit`, dynamic wave, {{inputs_used.swmm.options.routing_step_s}} s routing step. Conduits are open rectangular, invert elevations come from the design, and the outfall is free except in the tide runs. Node overflow level is the highest drain cope at the node, with no ponding: water above it is reported as overtopping (flooding) and lost. Sub-catchment parameters are in [Assumptions](#assumptions).
- **Tide boundary** (`sgdrain/tide.py`, `sgdrain/swmm_model.py`): SWMM TIMESERIES outfall at {{tide_inputs.tide.tide_step_min}}-minute steps from the predicted extremes, half-cosine between them. SWMM takes the larger of the sea level and critical/normal depth at the outfall, so a sea below the outfall invert behaves exactly like a free outfall (a test checks this). Open outfall: the junctions start filled to the sea level. Flap gate: SWMM's gated outfall.
- **Backwater** (`sgdrain/backwater.py`): standard step method on the energy equation with the Manning friction slope averaged over each step, from the outfall upstream, water level continuous through junctions, junction losses ignored. A sea below the normal-depth level leaves the design flow at normal depth; the drawdown towards a free outfall is ignored (conservative). The highest tolerable outfall level is found by bisection.
- **Pump and sump** (`sgdrain/pumpsump.py`): mass-curve (sequent-peak) storage for a constant pump capacity, exact for a piecewise-linear inflow. The SWMM check replaces the outfall node by a storage node of constant area that drains to the sea through a flap-gated outlet and is emptied by a variable-speed pump whose flow reaches capacity over the first few centimetres of sump depth.

## Assumptions

- **Synthetic catchment**: geometry, ground levels (arbitrary local datum, not SHD), land-use split and overland times are invented to look plausible. No public elevation data was used.
- **Lumped inflow**: each sub-catchment discharges at the upstream node of its reach. This is conservative for the rational method and identical in SWMM.
- **Minimum size**: COP Cl. 4.3.1 sets the {{inputs_used.cop.min_drain_dimension_mm}} mm minimum for roadside drains in a *closed* drainage system. It is applied here to every drain.
- **Size catalogue and gradient list**: illustrative. Real roadside drains follow the LTA standard details referenced in COP Cl. 9.1.2 / Drawing No. 1, which were not used.
- **SWMM hydrology** (sources in [docs/sources.md](docs/sources.md)): percent impervious = roads {{inputs_used.swmm.impervious_pct.road}}%, urban plots {{inputs_used.swmm.impervious_pct.urban}}%, vegetated {{inputs_used.swmm.impervious_pct.vegetated}}%. Overland flow length is {{inputs_used.catchment.overland_length_min_m}} to {{inputs_used.catchment.overland_length_max_m}} m depending on land use, and width = area / length. N-imperv {{inputs_used.swmm.hydrology.n_imperv}}, N-perv {{inputs_used.swmm.hydrology.n_perv}} (SWMM manual Table A.6). Depression storage {{inputs_used.swmm.hydrology.dstore_imperv_mm}} / {{inputs_used.swmm.hydrology.dstore_perv_mm}} mm (lower end of Table A.5). %Zero-Imperv {{inputs_used.swmm.hydrology.pct_zero_imperv}}. Green-Ampt clay loam from Table A.2: suction {{inputs_used.swmm.hydrology.ga_suction_mm}} mm, Ksat {{inputs_used.swmm.hydrology.ga_ksat_mm_hr}} mm/hr, initial deficit {{inputs_used.swmm.hydrology.ga_initial_deficit}}. None of this is calibrated.
- **Climate uplift**: one multiplier on every duration, taken from the range given for extreme *daily* rainfall (see Stress test).
- **Datum** (tide runs): A1, outfall ground at the COP minimum platform level for the southern coast; A2, mean of the predicted tide at SHD zero. Both are assumptions, covered by the sensitivity runs and the sweep (see [Tide and sea-level rise](#tide-and-sea-level-rise-at-the-outfall)).
- **Outfall setting**: the drains discharge straight to the sea, as for a drain outfall under COP Cl. 4.11, which also requires the outfall to discharge below the low tide level. A canal or reservoir between the estate and the sea is not modelled.

## Limitations

- Screening only: no structural, geotechnical, utility, maintenance-access or construction checks. No sumps, transitions or bends (COP Cl. 9), no dry-weather-flow channel detail (Cl. 7.3.1, Drawing No. 1), no culverts. The design and the rainfall stress test use a free outfall; tailwater is only in the tide runs.
- Tide runs: the tie between the catchment, SHD and Chart Datum rests on assumptions A1 and A2; the official Chart Datum to SHD conversion and MPA's tabulated tidal levels (for example mean high water springs) were not available. The tide comes from two months of predictions (November and December 2026, north-east monsoon), from a station the source does not name, rounded to {{tide_inputs.settings.tide_resolution_m}} m. No storm surge, waves or wind set-up; PUB's extreme sea levels for the CPCOP were not available. The V3 rise is added to 2026 predictions although it is measured from {{tide_inputs.coastal.v3_baseline}}. Vertical land movement is left to the V3 figures (relative sea level).
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

`pytest` runs {{mutation_report.baseline_passed}} tests offline. They cover:

- Manning and continuity invariants: capacity monotonic in width, depth and slope, Q = V A, and normal depth as the inverse of Manning.
- Rational-method arithmetic.
- Weighted C and the COP return-period rule.
- tc convergence, with each residual re-checked independently.
- Smallest-section optimality and COP criteria on every reach.
- The alternating-block window property.
- SWMM continuity below {{swmm_run_log.threshold_pct}}%, and a re-run of the SWMM design model checked against the committed results.
- Upsizing never shrinks a section and restores compliance.
- Tide and sea level: the official figures pinned to their sources, datum conversions, the tide interpolation and exact time-mean (on a made-up table), the committed tide extract (compared with the full table only where a local copy exists, so not in CI), the storm-aligned boundary, and that a sea below the outfall invert gives exactly the free-outfall SWMM result while a flap gate stops all backflow.
- Backwater: uniform flow is reproduced, the backwater curve against an independent numerical integration of the gradually-varied-flow equation, the highest tolerable outfall level bracketed, and the upsizing search.
- Pump and sump: the mass curve against closed-form results, and a SWMM run with a pump.
- README numbers checked against `results/`.

**Mutation test of the tests** ([`mutation/run_mutants.py`](mutation/run_mutants.py), report in [`results/mutation_report.json`](results/mutation_report.json)). The script plants {{mutation_report.n_mutants}} deliberate bugs, one at a time, in a scratch copy of the repo: {{mutation_report.groups.design.n}} in the drain design and {{mutation_report.groups.tide.n}} in the tide and sea-level code. It first checks that the unmodified suite passes and that every mutant compiles. For the drain design, the first round killed {{mutation_report.history.0.n_killed}} of {{mutation_report.history.0.n_mutants}} mutants. The survivors were {{mutation_report.history.0.survivors|list}}. The second survived because that level constraint never binds in this network. Tests were then added that check each section criterion flag on its own and force the level constraint to bind. The tide and sea-level mutants joined in round {{mutation_report.tide_first_round.round}}, where the tests as first written killed {{mutation_report.tide_first_round.n_killed}} of {{mutation_report.tide_first_round.n}}. Survivors: {{mutation_report.tide_first_round.survivors|list}}. The first was masked: the search re-checks its final network with the correct inverts, so a wrong trial still ended as "infeasible". Nothing recounted the backwater extent from the profiles, so the second went unseen. Tests were then added that require a failed search to report no enlargement and to match a re-run, that recount the extent station by station, and that recompute every committed sweep row. In the same round the design mutant for the SWMM conduit roughness was reported invalid rather than run: the new sump outlet repeats the expression it replaces, so its snippet now names the network conduit line. In the latest round (round {{mutation_report.round}}, {{mutation_report.baseline_passed}} tests) the suite killed **{{mutation_report.n_killed}} of {{mutation_report.n_mutants}}**: {{mutation_report.groups.design.n_killed}} of {{mutation_report.groups.design.n}} in the drain design, {{mutation_report.groups.tide.n_killed}} of {{mutation_report.groups.tide.n}} in the tide and sea-level code. Survivors: {{mutation_report.survivors|list}}.

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
