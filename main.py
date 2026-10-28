"""Evidence-bound API for the Space Industrial Base Atlas."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import OrderedDict, defaultdict, deque
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

BASE = Path(__file__).parent
DATA: dict[str, Any] = json.loads((BASE / "data.json").read_text(encoding="utf-8"))

# This is a conceptual reference workflow, not a claim about any program's commercial flow.
SOURCES = {
    "nasa-integration": {"title": "NASA Small Spacecraft: Integration, Launch, and Deployment", "url": "https://www.nasa.gov/smallsat-institute/sst-soa/integration-launch-and-deployment/"},
    "nasa-verification": {"title": "NASA Systems Engineering Handbook: Product Verification", "url": "https://www.nasa.gov/reference/5-3-product-verification/"},
    "nasa-product-integration": {"title": "NASA Systems Engineering Handbook: Product Integration", "url": "https://www.nasa.gov/reference/5-2-product-integration/"},
    "nasa-ssri": {"title": "NASA SSRI Knowledge Base: Integration", "url": "https://s3vi.ndc.nasa.gov/ssri-kb/topics/35/"},
}
PROCESS_MODEL = [
    ("materials", "Materials, parts & fabrication", "Prepare materials, procured parts and manufactured piece-parts for subsystem build.", ["requirements", "design data"], ["structures", "avionics", "power", "comms", "harness", "propulsion", "payload"], ["components", "materials"], ["manufacturing controls, inspection, material traceability"], ["supplier qualification evidence", "lot traceability and capacity", "part lead times"], "nasa-product-integration"),
    ("structures", "Structures & mechanisms", "Create the load-bearing structure and deployable/mechanical interfaces.", ["materials"], ["integration", "environmental-test"], ["components"], ["machining or composite equipment, dimensional inspection, interface control"], ["design-specific load margins", "qualification status by hardware", "facility capacity"], "nasa-product-integration"),
    ("avionics", "Avionics & flight computing", "Provide command, data handling and flight software execution functions.", ["materials"], ["functional-test", "integration"], ["subsystems", "components"], ["electronics assembly, programming, test equipment"], ["radiation/parts assurance", "software verification evidence", "production lead time"], "nasa-verification"),
    ("power", "Electrical power system", "Generate, store, regulate and distribute spacecraft electrical power.", ["materials"], ["functional-test", "integration"], ["subsystems", "components"], ["electrical test equipment, battery handling controls"], ["mission-specific power sizing", "battery qualification", "available production capacity"], "nasa-verification"),
    ("comms", "Communications & RF", "Provide RF interfaces for telemetry, tracking, command or payload data.", ["materials"], ["functional-test", "integration", "operations"], ["subsystems", "components", "operations"], ["RF measurement equipment, antenna test access, spectrum/interface controls"], ["link-budget compliance", "RF/environmental qualification", "ground-network access"], "nasa-verification"),
    ("propulsion", "Propulsion (mission-dependent)", "Provide delta-v, attitude support or orbit-change capability where required.", ["materials"], ["functional-test", "integration", "environmental-test"], ["subsystems", "components"], ["propellant safety controls, pressure systems, specialized test infrastructure"], ["whether propulsion is required", "hazard controls and qualification", "propellant and integration constraints"], "nasa-verification"),
    ("payload", "Payload integration", "Integrate the mission instrument or hosted payload with spacecraft interfaces.", ["materials", "avionics", "power", "comms"], ["functional-test", "integration"], ["subsystems", "integration"], ["interface control, calibration or payload-specific test equipment"], ["payload interface definition", "payload qualification evidence", "payload schedule and access"], "nasa-product-integration"),
    ("harness", "Harnesses & interconnections", "Route power and data through controlled electrical interconnections.", ["materials", "avionics", "power", "comms", "payload"], ["functional-test", "integration"], ["components"], ["wire processing, continuity/hipot testing, workmanship controls"], ["connector and parts assurance", "workmanship acceptance records", "length and routing constraints"], "nasa-verification"),
    ("functional-test", "Functional & acceptance test", "Verify allocated functions, interfaces and workmanship before or during integration.", ["avionics", "power", "comms", "payload", "harness"], ["integration", "environmental-test"], ["testing"], ["test automation, instrumentation, configuration control"], ["test levels and requirements", "test reports", "facility availability and schedule"], "nasa-verification"),
    ("integration", "Spacecraft assembly & integration", "Combine structure, subsystems and payload into an interface-controlled spacecraft.", ["structures", "avionics", "power", "comms", "propulsion", "payload", "harness", "functional-test"], ["environmental-test", "launch-integration"], ["integration", "subsystems"], ["clean handling, integration tooling, configuration and interface control"], ["assembly flow", "integration authority", "cleanliness and facility capability"], "nasa-ssri"),
    ("environmental-test", "Environmental qualification & acceptance", "Demonstrate performance against defined launch and space environments at the applicable verification level.", ["structures", "propulsion", "functional-test", "integration"], ["launch-integration"], ["testing"], ["vibration, thermal-vacuum, EMC or other test access as mission requires"], ["applicable environments and levels", "qualification versus acceptance basis", "test facility schedule"], "nasa-verification"),
    ("launch-integration", "Transport & launch-vehicle integration", "Prepare the flight article for shipment, deployer or launch-vehicle interfaces and campaign requirements.", ["integration", "environmental-test"], ["launch-campaign"], ["launch", "integration"], ["shipping controls, interface documentation, launch-provider requirements"], ["launch contract and interface approval", "campaign schedule", "transport controls"], "nasa-integration"),
    ("launch-campaign", "Launch campaign & deployment", "Execute launch-site processing, launch and spacecraft deployment.", ["launch-integration"], ["operations"], ["launch"], ["range and launch-site processes controlled by mission and provider"], ["launch service availability", "range approvals", "actual deployment configuration"], "nasa-integration"),
    ("operations", "Initial on-orbit operations", "Establish communications, commissioning and initial mission operations after deployment.", ["launch-campaign", "comms"], [], ["operations"], ["ground systems, command authority, mission operations procedures"], ["ground-network agreements", "operational readiness", "on-orbit performance"], "nasa-integration"),
]
CAPABILITY_MAP = {
    "materials": ["materials"], "components": ["materials", "structures", "harness"],
    "subsystems": ["avionics", "power", "comms", "propulsion", "payload", "integration"],
    "integration": ["integration", "payload"], "testing": ["functional-test", "environmental-test"],
    "launch": ["launch-integration", "launch-campaign"], "operations": ["operations", "comms"],
}
for company in DATA["companies"]:
    company["id"] = re.sub(r"[^a-z0-9]+", "-", company["name"].lower()).strip("-")
    company["capability_ids"] = sorted({cap for stage in company["stages"] for cap in CAPABILITY_MAP.get(stage, [])})
DATA["evidence_sources"] = list(SOURCES.values())
DATA["facilities"] = [{"id": f"{c['id']}-city", "organization_id": c["id"], "location_label": c["city"], "location_precision": "city", "status": "observed-location-label", "source": c["source"]} for c in DATA["companies"]]
DATA["capabilities"] = [{"id": p[0], "name": p[1]} for p in PROCESS_MODEL]
DATA["processes"] = [{"id": p[0], "name": p[1], "purpose": p[2], "inputs": p[3], "upstream": [], "downstream": p[4], "downstream_labels": [], "capability_ids": p[5], "requirements": p[6], "evidence_gaps": p[7], "evidence": [SOURCES[p[8]]], "relationship_type": "conceptual-engineering-dependency", "evidence_status": "public-engineering-source"} for p in PROCESS_MODEL]
for process in DATA["processes"]:
    process["upstream"] = [p["id"] for p in DATA["processes"] if process["id"] in p["downstream"]]
    process["downstream_labels"] = [next(p["name"] for p in DATA["processes"] if p["id"] == target) for target in process["downstream"]]
DATA["relationships"] = [{"from_id": p["id"], "to_id": target, "type": "conceptual-process-dependency", "evidence_status": "public-engineering-source", "source": p["evidence"][0]["url"]} for p in DATA["processes"] for target in p["downstream"]]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
MAX_PER_HOUR = int(os.getenv("ASK_MAX_PER_HOUR", "24"))
CACHE_TTL = int(os.getenv("ASK_CACHE_SECONDS", "21600"))
CACHE: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
REQUESTS: dict[str, deque[float]] = defaultdict(deque)
STOP = {"the", "what", "which", "could", "would", "from", "about", "where", "companies", "there", "that", "with", "have", "this", "are", "for", "who", "and", "does", "can", "how", "our", "into", "some", "a", "an", "in", "of", "to", "is", "it"}
SYNTHESIS_MARKERS = {"compare", "tradeoff", "prioritize", "scenario", "synthesis", "why", "strategy", "recommend", "risk", "bottleneck", "gap", "across"}
app = FastAPI(title="Space Industrial Base Atlas", version="0.3.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1200)
    stage: Optional[str] = None
    process_id: Optional[str] = None


def terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP


def score(company: dict[str, Any], words: set[str], stage: Optional[str]) -> int:
    hay = " ".join([company["name"], company["city"], company["sector"], company["description"], " ".join(company["stages"])]).lower()
    return sum(3 if word in company["name"].lower() else 1 for word in words if word in hay) + (4 if stage and stage in company["stages"] else 0)


def matches(question: str, stage: Optional[str]) -> list[dict[str, Any]]:
    words = terms(question)
    ranked = sorted(DATA["companies"], key=lambda c: (-score(c, words, stage), c["name"]))
    relevant = [c for c in ranked if score(c, words, stage) > 0]
    if not relevant and stage:
        relevant = [c for c in ranked if stage in c["stages"]]
    return (relevant or ranked)[:8]


def deterministic_answer(found: list[dict[str, Any]], stage: Optional[str]) -> dict[str, Any]:
    stage_name = next((s["name"] for s in DATA["stages"] if s["id"] == stage), None)
    lead = f"Registry matches for {stage_name}:" if stage_name else "Registry matches:"
    listings = "; ".join(f"{c['name']} ({c['city']}; {c['description']})" for c in found[:5])
    citations = [{"label": c["name"], "url": c["source"]} for c in found[:5]]
    return {"answer": f"{lead} {listings}. These are public-description matches and analytical stage classifications, not verified supplier relationships, flight qualification, capacity, availability, lead time, or bottlenecks.", "mode": "deterministic-registry", "matches": found, "citations": citations, "limitations": DATA["limitations"]}


def process_by_id(process_id: Optional[str]) -> Optional[dict[str, Any]]:
    return next((p for p in DATA.get("processes", []) if p["id"] == process_id), None)


def process_answer(process: dict[str, Any]) -> dict[str, Any]:
    candidates = [c for c in DATA["companies"] if set(c.get("capability_ids", [])) & set(process.get("capability_ids", []))]
    citations = [{"label": e["title"], "url": e["url"]} for e in process.get("evidence", [])]
    citations += [{"label": c["name"], "url": c["source"]} for c in candidates[:5]]
    return {
        "answer": f"{process['name']}: {process['purpose']} Inputs: {', '.join(process['inputs']) or 'not modeled'}. Downstream: {', '.join(process['downstream_labels']) or 'not modeled'}. Candidate organizations are public-description capability matches only; the Atlas does not assert that any named organization supplies this process.",
        "mode": "deterministic-process",
        "process": process,
        "matches": candidates,
        "citations": citations,
        "unknowns": process["evidence_gaps"],
        "limitations": DATA["limitations"],
    }


def should_synthesize(question: str) -> bool:
    q = question.lower()
    return any(marker in q for marker in SYNTHESIS_MARKERS) or len(terms(q)) > 13


def take_slot(request: Request) -> bool:
    ip, now = (request.client.host if request.client else "unknown"), time.time()
    q = REQUESTS[ip]
    while q and q[0] <= now - 3600: q.popleft()
    if len(q) >= MAX_PER_HOUR: return False
    q.append(now); return True


@app.get("/")
def homepage(): return FileResponse(BASE / "index.html")


@app.get("/api/data")
def get_data(): return DATA


@app.get("/healthz")
def health(): return {"ok": True, "version": "0.3.0", "organizations": len(DATA["companies"]), "facilities": len(DATA.get("facilities", [])), "processes": len(DATA.get("processes", [])), "openai_configured": bool(OPENAI_API_KEY)}


@app.post("/api/ask")
async def ask(payload: AskRequest, request: Request):
    question, found = payload.question.strip(), matches(payload.question, payload.stage)
    selected_process = process_by_id(payload.process_id)
    if selected_process and (not should_synthesize(question) or not OPENAI_API_KEY):
        return process_answer(selected_process)
    if not should_synthesize(question) or not OPENAI_API_KEY:
        return deterministic_answer(found, payload.stage)
    if not take_slot(request):
        return JSONResponse(deterministic_answer(found, payload.stage) | {"mode": "deterministic-rate-limit"}, status_code=429)
    cache_key = hashlib.sha256(f"{question.lower()}|{payload.stage or ''}|{OPENAI_MODEL}".encode()).hexdigest()
    cached = CACHE.get(cache_key)
    if cached and cached[0] > time.time():
        response = dict(cached[1]); response["mode"] = "openai-cached"; return response
    context = {"process": selected_process, "stages": DATA["stages"], "records": found, "limitations": DATA["limitations"]}
    instructions = """You are an evidence-bound industrial-base research assistant. Use only supplied registry and process-model data. Separate observed public descriptions, analytical classifications, conceptual generic dependencies, and unknowns. Never invent supplier relationships, production capacity, qualification, lead time, backlog, launch contracts, or bottlenecks. Sparse registry coverage is not proof of a gap. Cite supplied URLs only. Return JSON exactly: {\"answer\": string, \"citations\": [{\"label\": string, \"url\": string}], \"unknowns\": [string]}. Under 180 words."""
    body = {"model": OPENAI_MODEL, "instructions": instructions, "input": f"Question: {question}\n\nRegistry context:\n{json.dumps(context, ensure_ascii=False)}", "max_output_tokens": 550}
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}, json=body)
            response.raise_for_status()
        raw = response.json()
        output_text = ""
        for item in raw.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    output_text += content.get("text", "")
        if raw.get("status") == "incomplete" or not output_text:
            raise ValueError("incomplete or empty Responses API output")
        parsed = json.loads(output_text)
        allowed = {c["source"] for c in found}
        citations = [c for c in parsed.get("citations", []) if isinstance(c, dict) and c.get("url") in allowed][:8]
        result = {"answer": str(parsed.get("answer") or "").strip(), "mode": "openai-responses", "matches": found, "citations": citations, "unknowns": parsed.get("unknowns", []), "limitations": DATA["limitations"]}
        if not result["answer"]: raise ValueError("empty response")
        CACHE[cache_key] = (time.time() + CACHE_TTL, result)
        while len(CACHE) > 128: CACHE.popitem(last=False)
        return result
    except Exception:
        return deterministic_answer(found, payload.stage) | {"mode": "deterministic-api-fallback"}
