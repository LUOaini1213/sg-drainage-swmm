# Sources

Retrieval date for every online source below: **2026-11-06**. Page numbers are given as *printed page / PDF page*.

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

- No public elevation data was used. All levels are synthetic, on an arbitrary local datum.
