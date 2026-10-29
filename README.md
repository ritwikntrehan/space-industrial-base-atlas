# Space Industrial Base Atlas | v0.6

Independent Render/FastAPI app adapted conceptually from [SCHTMap](https://github.com/ritwikntrehan/oc-hard-tech-landscape). The original project is not modified.

## Features
- Interactive dependency graph for a representative small-satellite production-to-launch reference workflow: materials, structures, avionics, power, RF, propulsion, payload, harnessing, test, integration, launch and initial operations.
- Select a process to inspect generic upstream/downstream dependencies, potential controls, candidate public capability matches, cited engineering evidence, and missing information.
- Normalized API objects for organizations, city-level facility labels, capabilities, processes, typed conceptual dependencies, and evidence sources.
- Interactive city-centroid map and searchable 18-organization Orange County seed registry. City points are not facility-address assertions.
- A question-first homepage that turns evidence retrieval into validated map, process, and registry navigation actions.
- One response contract for answer text, citations, organization/facility/process/program IDs, suggested interface actions, unknowns, and evidence limitations.
- Seven governed funding, assistance, and ecosystem records covering federal SBIR/STTR, SpaceWERX paths, Caltech's Rocket Fund, and SoCal Deep Tech Week, with status and eligibility caveats.
- Deterministic `/api/ask` process, company, stage, facility, capability, and program retrieval. Anthropic's Messages API is optional and only used for complex synthesis; it is cached, rate-limited, server-side, and falls back deterministically.
- Bounded conversation history for contextual follow-ups. Returned citations, entity IDs, and actions are validated against Atlas data before the browser applies them.

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

The builder validates IDs, required evidence fields, statuses, dates, HTTPS sources, eligibility, and unknowns. See `docs/builder-question-audit.md` for the 15-question usefulness audit.

## Render
The included Render blueprint installs the official Anthropic Python SDK. Set `ANTHROPIC_API_KEY` in the service's Environment settings, never in Git, logs, browser code, or frontend responses. `ANTHROPIC_MODEL` defaults to `claude-sonnet-5` and can be changed without code edits. Claude access is optional: deterministic, source-linked answers and navigation remain available without credentials.

Do not expose the key through a `PUBLIC_` variable or add it to `index.html`. The browser only calls `/api/ask`; the server decides whether synthesis is needed.

## Data quality and interpretation

The dependency graph is a generic engineering reference model grounded in NASA systems-engineering and small-spacecraft material; it is not a verified serial process for every space program. Company-to-stage and company-to-capability matches are analytical classifications from public descriptions, not verified contractual relationships, flight qualifications, inventory, production rates, capacity, utilization, bottlenecks or launch access. Counts in this seed cohort are not evidence of sector-wide supply adequacy. Validate every stage attribution before external use.

Every dependency record is typed `conceptual-process-dependency`. There are deliberately no named supplier-to-customer or capacity relationships in v0.3. A real bottleneck assessment needs documented qualification status, facility/process capability, capacity and utilization, lead time, demand, actual supplier relationships, and mission/launch constraints.

## Current evidence limitations

The Atlas has three individually sourced facility records, seven program/ecosystem records, and an Orange County-centered organization seed cohort. It does not yet have complete shared-facility access data, live SAM.gov ingestion, people records, facility schedules, capacity, pricing, complete Los Angeles coverage, or verified supplier/customer relationships. The assistant says so instead of filling those gaps with model knowledge.

## Next iteration

Add governed shared-facility access records and credentialed, scheduled SAM.gov opportunity ingestion with expiration handling. Then add a bounded USAspending award-history view for relevant Southern California recipients.

## Tests

```bash
pytest -q
```
