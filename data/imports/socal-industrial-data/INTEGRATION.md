# Integration handoff — Space Industrial Base Atlas v0.7

Target repo: https://github.com/ritwikntrehan/space-industrial-base-atlas
Current deployed app during research: v0.6; this package has **not** been pushed or deployed.

## Start with the selected 250, not all 437

Use `website/demo_250_organizations.json` as the next large searchable organization set. `website/demo_250_organizations.csv` contains the same records. Do NOT publish the full raw research inventory by default. The 306 current-source pool in `website/candidate_organizations.json` is for further review; 131 historical-only or off-scope leads stay in canonical research storage.

The 250 includes 25 direct-space, 42 direct-or-aerospace, 147 industrial-supply-base, 31 adjacent industry candidates, and 5 ecosystem organizations. It is a **discovery catalog**, not a registry of 250 verified available space suppliers. Show source tier clearly and allow the user to filter out adjacent/directory-only candidates.

## Import procedure

1. Inventory the app's existing stable organization and facility IDs and seven program records. Preserve existing verified claims; do not overwrite the site's 20 organizations with our older abbreviated source descriptions.
2. Place package under an internal `data/imports/socal-industrial-data-v2/` directory or manage it as a versioned input. Keep source PSV files and full research tables server-side, and generate only compact website data.
3. Merge by stable ID and verified aliases. Original `OC-xxx` IDs remain preserved where known. Names and subsidiaries require review; do not automatically collapse acquisition/parent-company entities. Record merge decisions in a versioned alias/ID crosswalk.
4. Expose the 250 through map + registry + deterministic query retrieval with source tier and capability filters. The same query should return companies and industrial services across all seven counties, without requiring a Claude API call.
5. Map points: use city-center pins only if city is sourced and label as approximate. Use specific street-address pins only after geocoding official addresses and validating coordinate/site accuracy. If the UI can't display the location precisely, do not add invented coordinates.
6. Support filters for `direct-space`, `direct-or-aerospace`, `industrial-supply-base`, `adjacent-industrial`, and `ecosystem`; show process tags, source links, source confidence, location precision, and unknowns. Every result should link to supporting company or directory source. Empty websites should not produce fake "Visit Website" links.
7. Keep application programs, existing production graph, cited evidence, and Anthropic fallback functioning. Do not send all 250 organization records to the model at once. Retrieve relevant subsets deterministically.
8. Before release, inspect a sample across sources/geographies for wrong city, renamed firms, duplicate aliases, source-link failures, and process-tag overclaims; log unresolved entries rather than silently changing their confidence.
9. Push tested changes to GitHub (Render auto-deploys); verify health, 250 counted in public browse/search, map clustering, filters and 5 builder journeys including composites, machining, environmental test, RF hardware and startup programs. Do not fabricate any supplier capacities.

## Rebuild/QA

```bash
cd data/imports/socal-industrial-data-v2
python scripts/write_manifest.py
python scripts/build_package.py
python scripts/check_package.py
```

The selected file is deterministic. `qa/demo_250_audit.json` and `qa/demo_250_county_coverage.csv` give coverage counts. Track the same identifiers in Atlas data build so duplicates don't increase public totals.

## Acceptance

- Approximately **250 distinct, relevant, source-linked public organization records** after merge, or exactly the selected 250 if implementing a dedicated "industry directory" view. If existing Atlas organization IDs overlap, avoid double counting rather than inflating the headline.
- Clear differentiation between first-party, curated, and directory-only evidence, direct-space vs adjacent suppliers, and source-derived city points vs official facility addresses.
- Accessible company and facility details, basic capability filters and source URLs from the map and question-answer interface.
- Reproducible build and passing tests; release commit/deployment URL/QA counts reported back.
