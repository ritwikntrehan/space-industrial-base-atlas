# Space Industrial Base Atlas | v0.2

Independent Render/FastAPI app adapted conceptually from [SCHTMap](https://github.com/ritwikntrehan/oc-hard-tech-landscape). The original project is not modified.

## Features
- Clickable production-to-launch pathway with stage-specific company capabilities
- Interactive city-centroid company map and searchable Orange County seed registry (18 public descriptions from SCHTMap as of October 2026)
- Explicit industrial data gaps, without pretending that capacity or dependencies have been measured
- Source-linked company entries
- Deterministic `/api/ask` answers for direct lookups, plus OpenAI Responses API synthesis only where comparison or interpretation is requested
- In-memory response cache, per-client usage guard, and deterministic fallback if OpenAI is unavailable

## Local run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000.

## Render
Create a **new GitHub repository** and push these files. In Render, create a **new Blueprint** from that repository; it will read `render.yaml` and deploy to an independent Render web service. Set `OPENAI_API_KEY` in that **new service's** Environment settings, never in Git or browser code. OpenAI access is optional: deterministic registry answers remain available without it.

## Data quality and interpretation

The seven-stage chain is an illustrative generalized space hardware production workflow. It is not a verified serial process for every space program. Company-to-stage matches are analytical classifications from existing public descriptions in SCHTMap, not verified contractual relationships, flight qualifications, inventory, production rates, capacity, utilization, bottlenecks or launch access. The 'coverage' bars are **counts in this small seed cohort**, not evidence of sector-wide supply adequacy. Launch-stage capability is particularly sparse in this Orange County seed and must not be interpreted as a sector-wide shortage. Validate each stage attribution before use externally.

## Next iterations
1. Add a versioned facility/capability/evidence schema, qualification and supplier verification statuses.
2. Ingest complete SoCal seed universe (preserving map provenance), then enrich space-specialized firms and test facilities.
3. Add demand assumptions and scenarios; only quantify capacity after collecting supplier-reported or independently verified figures.
4. Add separate publicly documented startup support programs and program-to-company relationships.

## Tests

```bash
pytest -q
```
