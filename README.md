# Space Industrial Base Atlas | v0.3

Independent Render/FastAPI app adapted conceptually from [SCHTMap](https://github.com/ritwikntrehan/oc-hard-tech-landscape). The original project is not modified.

## Features
- Interactive dependency graph for a representative small-satellite production-to-launch reference workflow: materials, structures, avionics, power, RF, propulsion, payload, harnessing, test, integration, launch and initial operations.
- Select a process to inspect generic upstream/downstream dependencies, potential controls, candidate public capability matches, cited engineering evidence, and missing information.
- Normalized API objects for organizations, city-level facility labels, capabilities, processes, typed conceptual dependencies, and evidence sources.
- Interactive city-centroid map and searchable 18-organization Orange County seed registry. City points are not facility-address assertions.
- Deterministic `/api/ask` process, company, stage and capability retrieval. OpenAI Responses API is optional and only used for synthesis; it is cached, rate-limited and falls back deterministically.

## Local run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000.

## Render
Create a **new GitHub repository** and push these files. In Render, create a **new Blueprint** from that repository; it will read `render.yaml` and deploy to an independent Render web service. Set `OPENAI_API_KEY` in that **new service's** Environment settings, never in Git or browser code. OpenAI access is optional: deterministic registry answers remain available without it.

## Data quality and interpretation

The dependency graph is a generic engineering reference model grounded in NASA systems-engineering and small-spacecraft material; it is not a verified serial process for every space program. Company-to-stage and company-to-capability matches are analytical classifications from public descriptions, not verified contractual relationships, flight qualifications, inventory, production rates, capacity, utilization, bottlenecks or launch access. Counts in this seed cohort are not evidence of sector-wide supply adequacy. Validate every stage attribution before external use.

Every dependency record is typed `conceptual-process-dependency`. There are deliberately no named supplier-to-customer or capacity relationships in v0.3. A real bottleneck assessment needs documented qualification status, facility/process capability, capacity and utilization, lead time, demand, actual supplier relationships, and mission/launch constraints.

## Next iterations
1. Add separately sourced facility-level evidence where publicly appropriate, plus explicit qualification/process evidence records.
2. Complete one SoCal representative pathway with documented spacecraft integrator, test, and launch-infrastructure records.
3. Add supplier and program relationships only where public sources establish them; do not estimate capacity until evidence supports it.

## Tests

```bash
pytest -q
```
