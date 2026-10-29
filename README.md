# Space Industrial Base Atlas | v0.5

Independent Render/FastAPI app adapted conceptually from [SCHTMap](https://github.com/ritwikntrehan/oc-hard-tech-landscape). The original project is not modified.

## Features
- Interactive dependency graph for a representative small-satellite production-to-launch reference workflow: materials, structures, avionics, power, RF, propulsion, payload, harnessing, test, integration, launch and initial operations.
- Select a process to inspect generic upstream/downstream dependencies, potential controls, candidate public capability matches, cited engineering evidence, and missing information.
- Normalized API objects for organizations, city-level facility labels, capabilities, processes, typed conceptual dependencies, and evidence sources.
- Interactive city-centroid map and searchable 18-organization Orange County seed registry. City points are not facility-address assertions.
- A question-first homepage that turns evidence retrieval into validated map, process, and registry navigation actions.
- One response contract for answer text, citations, organization/facility/process IDs, suggested interface actions, unknowns, and evidence limitations.
- Deterministic `/api/ask` process, company, stage, facility, and capability retrieval. Anthropic's Messages API is optional and only used for complex synthesis; it is cached, rate-limited, server-side, and falls back deterministically.
- Bounded conversation history for contextual follow-ups. Returned citations, entity IDs, and actions are validated against Atlas data before the browser applies them.

## Local run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000.

## Render
The included Render blueprint installs the official Anthropic Python SDK. Set `ANTHROPIC_API_KEY` in the service's Environment settings, never in Git, logs, browser code, or frontend responses. `ANTHROPIC_MODEL` defaults to `claude-sonnet-5` and can be changed without code edits. Claude access is optional: deterministic, source-linked answers and navigation remain available without credentials.

Do not expose the key through a `PUBLIC_` variable or add it to `index.html`. The browser only calls `/api/ask`; the server decides whether synthesis is needed.

## Data quality and interpretation

The dependency graph is a generic engineering reference model grounded in NASA systems-engineering and small-spacecraft material; it is not a verified serial process for every space program. Company-to-stage and company-to-capability matches are analytical classifications from public descriptions, not verified contractual relationships, flight qualifications, inventory, production rates, capacity, utilization, bottlenecks or launch access. Counts in this seed cohort are not evidence of sector-wide supply adequacy. Validate every stage attribution before external use.

Every dependency record is typed `conceptual-process-dependency`. There are deliberately no named supplier-to-customer or capacity relationships in v0.3. A real bottleneck assessment needs documented qualification status, facility/process capability, capacity and utilization, lead time, demand, actual supplier relationships, and mission/launch constraints.

## Current evidence limitations

The Atlas has three individually sourced facility records and an Orange County-centered organization seed cohort. It does not yet have a startup-program database, customer-access terms, facility schedules, capacity, pricing, complete Los Angeles coverage, or verified supplier/customer relationships. The assistant says so instead of filling those gaps with model knowledge.

## Next iteration

Add a governed ingestion workflow for authoritative facility-access and startup-support program records, including eligibility, geography, effective dates, provenance, and record-expiration checks. This would make founder and facility-access questions more actionable without weakening the evidence boundary.

## Tests

```bash
pytest -q
```
