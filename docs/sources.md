# Sources

Retrieval date for the online sources in sections 1 to 5: **2026-11-06**; in section 6 (tide and sea level): **2026-11-09**. Page numbers are given as *printed page / PDF page*.

## 1. PUB Code of Practice on Surface Water Drainage

- **Document:** PUB, *Code of Practice on Surface Water Drainage*, Seventh Edition (Dec 2018) with amendments under Addendum No. 3 (April 2025). The cover reads "Seventh Edition - Dec 2018 / with amendments under Addendum No. 3 – April 2025". The PDF has 84 pages, and its metadata gives a creation date of 2025-04-23.
- **URL:** https://www.pub.gov.sg/-/media/PUB/PDF/Code-of-Practices-and-Submission-Guidelines/Surface-Water-Drainage/Code-of-Practice-on-Surface-Water-Drainage.pdf
- **SHA-256 of the copy used:** `e52ba4f37b5ca127d24d0f5c1c3cbd78c0342e33ce3775e762e478f36bb86d92`. `tools/digitize_idf.py` refuses a different file unless told otherwise.
- **Not redistributed.** Download it from PUB.

Only this consolidated PDF (with Addendum No. 3) was read. Earlier addenda were not checked separately.

| Used for | Clause / item | Page | Value as read |
|---|---|---|---|
| Peak runoff | 7.1.1 Rational Formula | 27 / 46 | Qr = (1/360) C I A; Qr m3/s, I mm/hr, A ha |
| Runoff coefficient | 7.1.2 table, as replaced by Addendum No. 3 S/No. 17 (amendment list on PDF p. 8) | 27 / 46 | Roads, highways, airport runways, paved up areas 1.00; Urban areas 0.90; Vegetated and pervious areas 0.45; a weighted C may be adopted for composite surfaces |
| IDF source | 7.1.3 Rainfall Intensity | 28 / 47 | I for duration = tc from the IDF curves in Appendix 4 |
| Return period | 7.1.3 table | 28 / 47 | < 100 ha: 10 yr; 100 to 1000 ha: 25 yr; > 1000 ha: 50 yr; airport runway or area specified by the Board: 100 yr |
| Time of concentration | 7.1.4 | 28 / 47 | tc = to + td; overland flow time to 5 to 15 min; td from the hydraulic properties of the drain |
| Flow assumption | 7.2.1 | 30 / 49 | steady uniform flow, one-dimensional analysis |
| Capacity | 7.2.2 Manning's Formula | 30 / 49 | Qc = (1/n) A R^(2/3) S^(1/2), R = A/P; Qc must be at least Qr |
| Roughness | 7.2.3 table | 30 / 49 | Concrete n = 0.0150 (also UPVC 0.0125, brick 0.0170, earth 0.0270, ...) |
| Minimum velocity | 7.3.1 | 31 / 50 | not lower than 1.0 m/s (self-cleansing); dry-weather-flow channel for low flows |
| Maximum velocity | 7.3.2 | 31 / 50 | concrete-lined drain at most 3.0 m/s or below critical velocity, whichever is lower |
| Sub-critical flow | 7.3.3 | 31 / 50 | Froude number within the range from 0.8 decreasing (implemented as Fr ≤ 0.8) |
| Freeboard | 7.3.4 | 31 / 50 | generally 15% of the depth of the drain |
| Minimum size | 4.3.1 (under 4.3 "Closed Drainage System") | 12 / 31 | internal width and clear depth of a roadside drain at least 600 mm (applied here to all drains, an assumption) |
| IDF curves | Appendix 4 "Rainfall Intensity-Duration-Frequency Curves for Singapore Island" | 49 / 68 | chart only. The time axis runs 2 to 1000 min, and curves are drawn from 5 min to about 700 min for return periods 2, 3, 5, 10, 15, 25, 50 and 100 yr. The digitised values are in `data/idf_cop_appendix4_digitised.csv` and the method in `data/idf_digitisation_meta.json` |

Read but **not** used: 7.1.5 maximum allowable peak runoff (C = 0.55, 10-yr, durations up to 4 h, for developments of 0.2 ha or more, p. 29 / 48); 9.2 transitions, 9.3 bends, 9.4 sumps, 9.5 connections (p. 34 / 53); Drawing No. 1 (LTA roadside drain details).

**What the COP does not specify, so this repo had to assume it:** a closed-form IDF equation (only the chart exists), a design hyetograph, a method for the overland time within 5 to 15 min, a size catalogue, and any parameter for dynamic models such as SWMM.

## 2. EPA SWMM

- **Manual:** Rossman, L.A. and Simon, M.A. (2022). *Storm Water Management Model User's Manual Version 5.2*. EPA/600/R-22/030, U.S. EPA, February 2022. https://www.epa.gov/system/files/documents/2022-04/swmm-users-manual-version-5.2.pdf

| Used for | Item | Page | Value |
|---|---|---|---|
| Green-Ampt soil (base: clay loam; sensitivity: sandy loam) | Table A.2 Soil Characteristics (source: Rawls et al. 1983) | 207 / 209 | clay loam K 0.04 in/hr, suction 8.27 in, porosity 0.464, field capacity 0.310; sandy loam K 0.43 in/hr, suction 4.33 in, porosity 0.453, field capacity 0.190 |
| Initial deficit definition | Infiltration editor, Green-Ampt parameters | 270 / 272 | "for a completely drained soil", porosity minus field capacity |
| Depression storage | Table A.5 (source: ASCE 1992) | 210 / 212 | impervious 0.05-0.10 in; lawns 0.10-0.20 in (lower ends used) |
| Overland Manning n | Table A.6 (source: McCuen et al. 1996) | 211 / 213 | smooth asphalt 0.011; grass, short prairie 0.15 |
| %Zero-Imperv | Section 2.2 example project defaults | 22 / 24 | 25 |

- **Engine:** EPA SWMM 5.2 solver (version code `52004`, i.e. 5.2.4) as packaged in `swmm-toolkit==0.17.0` on PyPI (Open Water Analytics), called through `swmm.toolkit.solver.swmm_run`.

## 3. Climate uplift

- **Source:** Meteorological Service Singapore / Ministry of Sustainability and the Environment joint news release, *Latest Climate Projections For Singapore Show Intensifying Urban Heat And More Wet & Dry Extremes*, 5 January 2024 (Third National Climate Change Study, V3). https://www.nea.gov.sg/media/news/news/index/latest-climate-projections-for-singapore-show-intensifying-urban-heat-and-more-wet-dry-extremes
- **Used:** paragraph 7. Extreme daily rainfall is projected to increase in all seasons, with increases of about 6 to 92 per cent in the inter-monsoon months of April and May. Footnote 6 defines extreme daily rainfall as the 99.9th percentile of daily rainfall over 1995-2014.
- **Caveats:** the release does not attach an emissions scenario or time horizon to that sentence. It concerns *daily* totals, not the 5 to 20 minute intensities that size urban drains. Using the two ends as uniform multipliers is this project's assumption, and the upper end is a bounding case.
- **Context, not used numerically:** a Parliamentary reply on flood prevention (5 February 2018) says PUB has raised drainage design standards since 2011 so that drains can handle up to 45 per cent higher rainfall intensities. https://www.nccs.gov.sg/media/parliamentary-reply-by-masagos-zulkifli-minister-of-the-environment-and-water-resources-on-flood-prevention/ That figure compares new standards with old ones. It is not a climate allowance, so it is not used here.

## 4. Design hyetograph

- Chow, V.T., Maidment, D.R. and Mays, L.W. (1988). *Applied Hydrology*. McGraw-Hill, chapter 14 "Design Storms", alternating block method. The exact section number was not verified against the book for this project. The algorithm is fully specified in `sgdrain/hyetograph.py`, and its defining property is unit-tested.

## 5. Data not used

- No public elevation data was used. All levels are synthetic, on an arbitrary local datum. The tide runs tie that datum to SHD by an explicit assumption (section 6.6).

## 6. Tide, sea level and datum (tide/SLR runs, retrieved 2026-11-09)

### 6.1 PUB Code of Practice on Surface Water Drainage (same PDF as section 1)

| Used for | Clause / item | Page | Value as read |
|---|---|---|---|
| Datum assumption A1 | 2.1.1(a)(i) Minimum Platform Level, General Developments | 6 / 25 | not lower than "4.0m above Singapore Height Datum for developments along the southern coast; and 4.5m above Singapore Height Datum for developments along the northern coast"; or 300 mm above the adjacent road/ground level; or as specified by the Board; whichever is the highest. Cl. 2.1.1(b) and (c) repeat the 4.0 / 4.5 m SHD values (with 600 mm and 1 m above the road) |
| Context | 2.3 Minimum Reclamation Level | 9 / 28 | 4.0 m SHD southern coast, 4.5 m SHD northern coast, or as specified by the Board |
| Outfall setting | 4.11 Outfall Structure for Drain Connecting to the Sea | 15 / 34 | outfalls extended under and beyond the sand bar "to discharge flow at below the low tide level"; sea-bed at least 500 mm below the outfall invert at the point of discharge |
| Context | Terminology, "Storm Water Drainage System" | 3 / 22 | includes "any weir, grating, float boom, gauge, tidegate, sump, storage pond, pumping station ..." |
| Pump, for scale only | 10.1(a) Pumped Drainage System | 38 / 57 | pumping capacity for "storm water ingress of not less than 150 millimetres per hour from the entire source catchment area"; P = I A / (3.6 x 10^6), P in m3/s, I in mm/hr, A in m2. Clause 10 is referred to from Cl. 4.9 (underground facilities); it does not govern estate outfalls |
| Context | Introduction | 1 / 20 | "the ground levels of some 30% of Singapore are less than 5 m above mean sea level" |

The COP does not specify a tailwater, tide level or joint probability for drain design (searched: tide, tidal, tailwater, backwater, sea level).

### 6.2 PUB Code of Practice on Coastal Protection (CPCOP)

- **Document:** PUB, *Code of Practice on Coastal Protection*, First Edition, June 2026 (cover; PDF title adds "New requirements will take effect in 2028"). 80 pages, PDF creation date 2026-06-12.
- **URL:** https://www.pub.gov.sg/-/media/PUB/PDF/Code-of-Practices-and-Submission-Guidelines/Coastal-Protection/CPCOP-First-Edition-June-2026.pdf
- **SHA-256 of the copy read:** `78d127e849b21f268a353bf2c3cc1078cddcb15e885625ba31c5dfbef0ccc99d`. Not redistributed.
- Press release: PUB, *New Code of Practice on Coastal Protection to strengthen Singapore coastal resilience*, 17 June 2026: "The CPCOP will take effect from 2028." https://www.pub.gov.sg/Resources/News-Room/PressReleases/2026/06/New-Code-of-Practice-on-Coastal-Protection-to-strengthen-Singapore-coastal-resilience

| Used for | Clause / item | Page | Value as read |
|---|---|---|---|
| Sea-level scenarios +0.7 m and +2.15 m | 2.1(a)(i), 2.1(a)(ii), 2.1(b)(i), 2.2 | 12 / 13 | "CPL computed for 0.7m RMSLR planning scenario"; "CPL computed for 2.15m RMSLR planning scenario". No year is attached to either scenario anywhere in the code |
| Same scenarios, backflow | 6.1 Hydraulic Connection | 18 / 19 | process water pipes designed so that "backwater flow will not cause flooding in the premises they serve", design condition "an ESL of 2.15m RMSLR planning scenario" (more than 30 years of lease) or "0.7m" (30 years or less) |
| Definitions | Terminology | 7 / 8 | Design Water Level: surge-tide level (joint probability of surge and wave events) plus RMSLR. Extreme Sea Level: surge-tide level (without that joint probability) plus RMSLR. Hydraulic Connection: "A drain, channel or pipe that cuts across the APB and is influenced by the sea level" |
| Definitions | Terminology | 8 / 9 | SHD: "Vertical reference datum as determined by the Singapore Land Authority (2015). Conversion of CD to SHD can be obtained from the Hydrographic Division of the Maritime and Port Authority of Singapore (MPA)." Transient coastal flooding includes "seawater backflow through drains" |
| Surge not available | 4.3 and footnote 2 | 14 / 15 | ESL, DWL and wave parameters are "available on PUB's website"; footnote: "currently under review and will be provided on PUB's website when available" |
| Context | 4.8 | 16 / 17 | ground protected by a coastal barrier or tidal gate not lower than the Maximum Water Level prescribed by the Board |
| Context | Annex A, item 1(d) | 59 / 60 | all heights for planning and engineering works in SHD |

### 6.3 Third National Climate Change Study (V3), sea level

- **Report:** Centre for Climate Research Singapore / MSS, *V3 Report for Stakeholders*, Chapter 5 "Climate Change Projections for Singapore". Chapter PDF: https://assets.app.optical.gov.sg/mss-int/production/published/collections/pages/0cfd22b1-6331-4fed-9556-56b1a4cc503a/04c58982-b2bd-405d-a33b-ee8230a30f3a.pdf, linked from https://www.mss-int.sg/v3-climate-projections/resources/v3-reports. 18 pages (printed pp. 49 to 66), SHA-256 `5271bfeaa0ed5b1706e6582f516e20e894e29ca7e10c6a10c1c7d4b3bb7637b0`. Not redistributed.
- **Section 5.14.2** (p. 62 / chapter PDF p. 14): medium-confidence projections; "All sea-level projections are computed in relation to the AR6 baseline period of 1995-2014."
- **Table 5.10** (p. 63 / chapter PDF p. 15), "Projected relative sea-level rise and global-mean sea-level rise by 2100 and 2150 (median and likely range in brackets), under three emission scenarios (SSP1-2.6, SSP2-4.5 and SSP5-8.5) of medium confidence". Values used or quoted (m):

| Gauge | SSP1-2.6 2100 | SSP1-2.6 2150 | SSP2-4.5 2100 | SSP2-4.5 2150 | SSP5-8.5 2100 | SSP5-8.5 2150 |
|---|---|---|---|---|---|---|
| Sultan Shoal | 0.51 (0.34-0.74) | 0.82 (0.50-1.24) | 0.63 (0.46-0.88) | 1.05 (0.72-1.52) | 0.85 (0.66-1.15) | 1.47 (1.03-2.12) |
| Tanjong Pagar | 0.44 (0.24-0.69) | 0.71 (0.35-1.16) | 0.56 (0.36-0.82) | 0.94 (0.56-1.43) | 0.78 (0.56-1.10) | 1.36 (0.89-2.02) |
| Singapore average | 0.45 +/- 0.03 | 0.72 +/- 0.05 | 0.57 +/- 0.04 | 0.95 +/- 0.06 | 0.79 +/- 0.04 | 1.37 +/- 0.06 |

  The run uses one value: **1.15 m, Sultan Shoal, SSP5-8.5, 2100, top of the likely range**. The text calls the top of the gauge ranges "the upper bounds (83rd percentile)" (p. 64 / chapter PDF p. 16) and says Sultan Shoal has the largest projected rise (p. 63). The chapter's key messages (p. 49 / chapter PDF p. 1): "Mean sea levels to rise by up to 1.15m by 2100 and up to around 2m by 2150."
- **News release** (section 3): paragraph 8, "projected to rise by 0.23m to 1.15m by end century, and by up to around 2m by 2150 under the high emissions scenario"; Annex A row "Increase in mean sea level (m)": SSP1-2.6 0.23 to 0.74, SSP2-4.5 0.34 to 0.88, SSP5-8.5 0.54 to 1.15.

### 6.4 Tide predictions

- **Source:** NEA, *Tide Timings*, https://www.nea.gov.sg/weather/tide-timings, retrieved 2026-11-09. Tables of predicted high (H) and low (L) water for November and December 2026. Page note: "The tidal information is obtained from the Maritime and Port Authority (MPA) of Singapore. Tidal height is in metres above the 'Chart Datum' ...". The page does not name the station or the time zone (Singapore time assumed).
- **Table (kept locally, not in the repository):** 236 rows (118 H, 118 L) copied from the page tables into `data/local/tide_predictions_mpa_2026-11_12.csv` (git-ignored); SHA-256 `547a91f215567b75b0ffeda954dfcf1624e55a9110ad3880f0248eb3d181b9db`. Rows were spot-checked against the page (1, 10 and 30 November; 1, 8, 26, 27 and 31 December). NEA's Terms of Use (https://www.nea.gov.sg/terms-of-use, read 2026-11-09) say the site's contents "shall not be reproduced, republished, uploaded, posted, transmitted or otherwise distributed in any way, without the prior written permission of NEA", so the table is not committed. Whether the same predictions are available elsewhere under an open licence was not checked.
- **Extract (committed):** `data/tide_extract_mpa_2026-11_12.json`, written by `scripts/make_tide_extract.py` from the local table: the table's statistics (counts, first and last time, highest high water, mean high and low water, lowest low water), its unrounded time-mean level, and the three predicted extremes that bracket the simulated window (26 December 2026: low water 06:26, 1.8 m; high water 12:01, 3.4 m; low water 18:52, 0.2 m, all above Chart Datum). The runs read only the extract. `tests/test_tide.py` rebuilds the extract from the table and compares it where a local copy exists; without one (as in CI) that test is skipped, so the statistics in the extract cannot be re-derived from the repository alone.
- **To rebuild:** copy the November and December 2026 tables from the NEA page into the local file (header `date,time,height_m_cd,type`), check the SHA-256 above, and run `python scripts/make_tide_extract.py`. NEA replaces the tables over time, so a later copy may cover other months.
- **MPA tide tables not used:** MPA's *Singapore Tide Tables* (https://www.mpa.gov.sg/who-we-are/newsroom-resources/publications/singapore-tide-tables) include "a table of tidal levels, such as Mean High Water Springs and Mean Low Water Springs, at various stations referenced to CD", but are sold through chart distributors and were not obtained. So **no official MHWS, HAT or MSL figure is used**; the runs use the highest predicted high water of the two months instead.

### 6.5 SHD, and the combined extreme

- NCCS, *Impact of Climate Change in Singapore*, https://www.nccs.gov.sg/singapores-climate-action/impact-of-climate-change-in-singapore (page last updated 11 August 2026), footnote 1: "Singapore Height Datum is the reference established based on the mean sea level determined at the tide gauge located at Victoria Dock in Tanjong Pagar between 1935-1937." Same page: "about 30 per cent of our island being less than 5 m above the Singapore Height Datum".
- MSE, *2nd Reading of the Coastal Protection Bill - Opening Speech by Minister Grace Fu*, 6 March 2026, https://www.mse.gov.sg/latest-news/2nd-reading-of-the-coastal-protection-bill---opening-speech-by-minister-grace-fu/ : V3 "projects that our sea levels may rise up to 1.15m by the end of this century, reaching up to 5 metres above today's mean sea level when coupled with storm surges and high tides." The MSE release introducing the Bill (3 February 2026, https://www.mse.gov.sg/latest-news/introduction-of-coastal-protection-bill-/, footnote 1) gives the same figures. Quoted for context; no surge is modelled.

### 6.6 What is assumed, not sourced

- **A1:** outfall ground = 4.0 m SHD (COP Cl. 2.1.1(a)(i), southern coast). The catchment is synthetic; this is a choice, not a site level.
- **A2:** the time-mean of the Nov-Dec 2026 predictions (1.9418 m CD) = 0.0 m SHD. The official CD-to-SHD conversion (CPCOP terminology: obtainable from MPA's Hydrographic Division) was not obtained. A 2022 SLA presentation to UN-GGIM lists "Harmonisation of Singapore Height Datum and Chart Datum" as a current challenge (https://ggim.un.org/meetings/2022/3rd-WG-MGI/documents/Session%203-Victor%20Khoo.pdf, slides 5 and 22); its datum diagram (slide 16) could not be read reliably from the PDF text and is not used.
- Half-cosine interpolation between predicted extremes; high water at the storm peak.
- Standard step method: Chow, V.T. (1959). *Open-Channel Hydraulics*. McGraw-Hill. The chapter was not checked against the book; the algorithm is fully specified in `sgdrain/backwater.py` and tested against an independent integration.

### 6.7 Could not verify

- Whether PUB has published the CPCOP coastal hydraulic boundary parameters (ESL, DWL) since June 2026: PUB's professionals pages returned HTTP 403 to the automated fetch.
- The horizon years behind the CPCOP's 0.7 m and 2.15 m scenarios (not in the code, the press release or the Bill's second-reading speech).
- The station and the time zone of the NEA tide table.
