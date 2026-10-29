# Southern California Space Industrial Data — v2 / 2026-10-29

**Research and integration package, not a website deployment.** A selected set of **250** relevant organizations and industrial-service candidates is ready for Atlas integration. The existing live Atlas is not changed by this archive.

## Recommended Codex input

- `website/demo_250_organizations.json` or `.csv`: **250** source-linked, seven-county demo records, prioritized for builder relevance. Every row requires publication review. No current supplier/qualification/capacity status is asserted.
- `website/candidate_organizations.json`: **306** other broad and adjacent current-source candidates, including the 250.
- `website/verified_facilities.json`: **20** individually sourced facility/location records, not all exact geocoded points.
- `organizations.csv`, `locations.csv`, `facilities.csv`, `capabilities.csv`, `relationships.json`: complete linked research dataset.
- `source_manifest.json` and `source/*.psv`: source ledger, per-row links, reproducible compact source extracts.
- `scripts/build_package.py`, `scripts/write_manifest.py`, `scripts/check_package.py`: reproducible, Python-standard-library-only build and validation.
- `INTEGRATION.md`, `DATA_AUDIT.md`, `qa/`: selection rules, documentation and QA.

## Scope

The universe includes 437 organizations after name-normalized deduplication; the live-demo set includes 250: direct-space firms, aerospace firms, component and materials providers, precision/advanced manufacturers, specialty coatings, testing and calibration providers, and ecosystem operators. Direct SpaceTech and broader aerospace suppliers must be presented distinctly.

The new second pass added 164 manually selected SoCal aerospace directory rows and 35 further regional sector observations, rechecking 11 organizations with first-party descriptions and adding eight official facility records. Some records overlap with the first package and are deduplicated by normalized name (not by assumed parent/subsidiary ownership).

**Warning:** 170 of the 250 are supported only by secondary 2026 directory/sector listings; 63 are curated 2026 SCHTMap evidence records; 17 have first-party site verification in this package. Display source tier visibly. These are not 250 flight-qualified, active, available space suppliers.

Historical NASA supplier-only records remain research-only, with historical provenance and without current supplier or site-status claims. The default 250 excludes them.

Every record is a current-source *candidate*, not a guaranteed operating supplier. No RFQ, AS9100 qualification, capacity, schedule, pricing or supplier relationship should be inferred from broad directory membership.

## Review and rebuild

From this directory:

```bash
python scripts/write_manifest.py
python scripts/build_package.py
python scripts/check_package.py
```

See `DATA_AUDIT.md` for detailed evidence and `INTEGRATION.md` for Codex instructions. Source CSVs contain URLs for audit. Directory source pages are discovery provenance, not permission to reproduce full third-party profiles.
