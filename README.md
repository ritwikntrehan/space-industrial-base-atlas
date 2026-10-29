# Space Industrial Base Atlas | v0.9

Independent Render/FastAPI app adapted conceptually from [SCHTMap](https://github.com/ritwikntrehan/oc-hard-tech-landscape). The original project is not modified.

## Features
- Interactive dependency graph for a representative small-satellite production-to-launch reference workflow: materials, structures, avionics, power, RF, propulsion, payload, harnessing, test, integration, launch and initial operations.
- Select a process to inspect generic upstream/downstream dependencies, potential controls, candidate public capability matches, cited engineering evidence, and missing information.
- Normalized API objects for organizations, city-level facility labels, capabilities, processes, typed conceptual dependencies, and evidence sources.
- Clustered seven-county discovery map and searchable 250-organization registry with county, industrial-role, capability, and evidence-tier filters.
- Twenty individually sourced facility/site records. Only separately validated coordinates are treated as specific map points; un-geocoded addresses remain text.
- Twenty-five reusable evidence dossiers expose products/services, mapped production processes, documented materials, experience basis, linked facilities, source citations, review dates, explicit qualification notes, and unknowns.
- Transparent supplier-candidate answers explain capability, geography, evidence tier, profile depth, and relevant production processes without opaque scores or capacity claims.
- A question-first homepage that turns evidence retrieval into validated map, process, and registry navigation actions.
- One response contract for answer text, citations, organization/facility/process/program IDs, suggested interface actions, unknowns, and evidence limitations.
- Seven governed funding, assistance, and ecosystem records covering federal SBIR/STTR, SpaceWERX paths, Caltech's Rocket Fund, and SoCal Deep Tech Week, with status and eligibility caveats.
- Deterministic `/api/ask` process, company, stage, facility, capability, and program retrieval. Anthropic's Messages API is optional and only used for complex synthesis; it is cached, rate-limited, server-side, and falls back deterministically.
- Bounded conversation history for contextual follow-ups. Returned citations, entity IDs, and actions are validated against Atlas data before the browser applies them.
- A shared analysis workspace for builder and ecosystem questions: interpreted objective, pathway requirements, documentation coverage, practical next steps, unknowns, citations, and synchronized map/graph/registry actions.
- An ecosystem-intelligence preview that reports organization, dossier, and sourced-facility counts by production stage. These are documentation metrics, never claims of regional capacity or supply adequacy.
- Shareable `?q=` URLs that restore and run the same evidence-bound question.
- A versioned 30-question audit corpus spanning builders, small companies, buyers, funders, conveners, and adversarial prompts. Six anchor questions are release-gated in the automated tests.

## Local run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000.

## Data build

The versioned data layout separates `data/source`, `data/canonical`, and `data/website`. `data/source_manifest.json` records provider, access, coverage, reuse constraints, update frequency, authentication, and ingestion status.

After changing curated source records, rebuild the canonical and website payloads:

```bash
python scripts/build_data.py
```

The builder validates IDs, required evidence fields, statuses, dates, HTTPS sources, eligibility, unknowns, all seven counties, the 250-record selected import, and the 17/63/170 evidence-tier breakdown. It also writes an explicit imported-ID to Atlas-ID crosswalk. See `docs/builder-question-audit.md` for the usefulness audit.

## Render
The included Render blueprint installs the official Anthropic Python SDK. Set `ANTHROPIC_API_KEY` in the service's Environment settings, never in Git, logs, browser code, or frontend responses. `ANTHROPIC_MODEL` defaults to `claude-sonnet-5` and can be changed without code edits. Claude access is optional: deterministic, source-linked answers and navigation remain available without credentials.

Do not expose the key through a `PUBLIC_` variable or add it to `index.html`. The browser only calls `/api/ask`; the server decides whether synthesis is needed.

## Data quality and interpretation

The dependency graph is a generic engineering reference model grounded in NASA systems-engineering and small-spacecraft material; it is not a verified serial process for every space program. Company-to-stage and company-to-capability matches are analytical classifications from public descriptions, not verified contractual relationships, flight qualifications, inventory, production rates, capacity, utilization, bottlenecks or launch access. Counts in this seed cohort are not evidence of sector-wide supply adequacy. Validate every stage attribution before external use.

Every dependency record is typed `conceptual-process-dependency`. There are deliberately no named supplier-to-customer or capacity relationships in v0.3. A real bottleneck assessment needs documented qualification status, facility/process capability, capacity and utilization, lead time, demand, actual supplier relationships, and mission/launch constraints.

## Current evidence limitations

The Atlas has 250 discovery organizations, 20 individually sourced facility/site records, and seven program/ecosystem records. Of the selected organizations, 17 have first-party verification in the supplied research package, 63 are previously curated source snapshots, and 170 are directory/sector candidates requiring primary verification. It does not assert supplier availability, capacity, pricing, qualification, or customer relationships.

## Demo boundary

v0.9 is the Rahul Singh / SoCal Deep Tech continuation demo. It demonstrates the interaction and evidence-governance harness using existing sourced records. Broader data acquisition, a community correction workflow, procurement-grade validation, and quantitative bottleneck analysis remain continuation decisions rather than hidden claims in this release.

## Tests

```bash
pytest -q
```
