# Southern California industrial-base research audit — second pass

Reviewed: 2026-10-29

## Deliverable and scope

| Item | Result |
|---|---:|
| Unique organizations in full research universe | 437 |
| Current-source website candidates (including wider adjacent firms) | 306 |
| Selected **demo shortlist** | **250** |
| Research-only/historical and out-of-scope rows | 131 |
| Organization/capability claims | 765 |
| City-level location observations | 443 |
| Source-backed facility/site records | 20 |
| Typed research relations | 896 |
| Documented data-source entries | 22 |

The current public website has **not been updated** by this data research. Codex must integrate and deploy the 250-row file.

## Evidence tiers in the selected 250

- **17** organization records with an official company-site verification in the package.
- **63** previously curated SCHTMap 2026 records (varying source quality, not independently reverified this turn).
- **170** directory/sector-listing records requiring direct company checks before any statement beyond the directory's reported industry or process categories.

A source's date is the date the directory was reviewed, not proof that every business is operational today. A website listing does not establish open capacity or aerospace/space qualification. All `publication_review_required` flags are true.

## Industry roles

- 25 direct-space
- 42 direct-or-aerospace
- 147 industrial supply base
- 28 adjacent-industrial candidates
- 3 adjacent-industrial
- 5 ecosystem organizations

The adjacent category is necessary: a maker may need tooling, processing, RF or electronics even if the provider has not disclosed space-flight experience. Do not commingle with confirmed space mission activity.

## Counties represented (250 subset)

| County | Records |
|---|---:|
| Orange | 97 |
| Los Angeles | 81 |
| San Diego | 35 |
| Riverside | 13 |
| San Bernardino | 12 |
| Ventura | 11 |
| Santa Barbara | 1 |

Coverage is based on **source availability**, not actual establishment counts. Santa Barbara is notably underrepresented. Missing counties, facilities and suppliers should be expanded based on independent sources; source counts are not supply adequacy metrics.

## What was added in second pass

1. **164** aerospace supplier listings from current California manufacturer directory pages, manually restricted to plausibly SoCal city names and published process tags. Ambiguous/fictitious city labels in the source directory were omitted; a few older city names remain and require precise verification. Source page is preserved for each individual row.
2. **35** selective additional regional space/industrial firms from the San Diego Regional EDC, AIAA San Diego, DefDex and Santa Ana Chamber. Many overlap the existing inventory; the upstream build merges them by name.
3. **11** source-backed official company descriptions including Carbon by Design, Applied Composites, VACCO Industries, Terra Universal, Micro Quality Calibration, Glenair, Ultramet, Advanced Test Equipment Corporation, Boeing, Northrop Grumman, and SpaceX. The direct official sources clarify why the business matters, not verified commercial supplier accessibility.
4. **8** newly sourced company-operated site records with official street addresses (no fabricated geocodes); total 20 site records with previous facilities.
5. A prioritized, 250-item import file with conservative evidence labels and a seven-county coverage audit.

## Source and licensing caveats

The previous package's 2019 NASA supplier names are historical-only research leads and are excluded from the demo. The first-party official sources and user-owned SCHTMap seed are distinguished from directory excerpts. For commercial directories such as NORAMARK and DefDex, the extract stores only limited company identity, reported city, industry/process facts and links, **not** proprietary directory profile text. Check each site's terms before redistributing their material; facts are not endorsements.

Some claimed process categories come only from a directory and require manufacturer confirmation; a generic `Machining` tag is not evidence of 5-axis capacity, spaceflight qualification, export eligibility, prices, lead times or available production slots. Specific address lines are limited to separately sourced facilities. Coordinates are intentionally absent for newly added address-backed sites pending geocoding.

## QA and unresolved issues

- `scripts/check_package.py` asserts unique IDs, FK integrity, 250 shortlist rows, all seven counties, no historical-only default entries, source links, provenance and capacity-claim guardrails.
- Names with shared identity, mergers, acronyms and multiple facilities need targeted entity-resolution review. For example, `Thirty Two Machine` and `Thirty-Two Machine and Design` are not automatically merged without affirmative alias evidence.
- `locations.csv` is city-only even where a separate address exists in `facilities.csv`; this prevents false facility precision.
- An automated primary-site crawl of all 250 has **not** been performed. Source-page availability and the operation of all 250 companies have **not** been individually confirmed.
- The website's existing 20 organizations, 7 startup-program records, and validated facilities should remain authoritative when an imported candidate conflicts.
- Do not treat `site_launch_250` ranking as a competitive supplier ranking or measure of production capability; it is an editorial demo selection focused on discoverability and source diversity.

## Next high-leverage validation

Improve direct company websites and facility locations for the 170 directory-only entries in priority order (machine shops, composites, test/qualification providers, precision components, avionics, electronics), and continue expansion into Santa Barbara/Ventura, San Diego, and the Inland Empire. Keep programs/opportunities in their existing data tables.
