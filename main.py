"""Evidence-bound API for the Space Industrial Base Atlas."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from collections import OrderedDict, defaultdict, deque
from pathlib import Path
from typing import Any, Optional

from anthropic import AsyncAnthropic
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Literal

BASE = Path(__file__).parent
LOGGER = logging.getLogger("atlas.synthesis")
DATA: dict[str, Any] = json.loads((BASE / "data.json").read_text(encoding="utf-8"))
DATA["programs"] = json.loads((BASE / "data" / "website" / "programs.json").read_text(encoding="utf-8"))["programs"]
DATA["companies"] = json.loads((BASE / "data" / "website" / "organizations.json").read_text(encoding="utf-8"))["organizations"]

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
    company["stages"] = company.get("process_ids", [])
    company["capability_ids"] = company.get("process_ids", [])
DATA["evidence_sources"] = list(SOURCES.values())
DATA["facilities"] = []
DATA["capabilities"] = [{"id": p[0], "name": p[1]} for p in PROCESS_MODEL]
DATA["processes"] = [{"id": p[0], "name": p[1], "purpose": p[2], "inputs": p[3], "upstream": [], "downstream": p[4], "downstream_labels": [], "capability_ids": p[5], "requirements": p[6], "evidence_gaps": p[7], "evidence": [SOURCES[p[8]]], "relationship_type": "conceptual-engineering-dependency", "evidence_status": "public-engineering-source"} for p in PROCESS_MODEL]
for process in DATA["processes"]:
    process["upstream"] = [p["id"] for p in DATA["processes"] if process["id"] in p["downstream"]]
    process["downstream_labels"] = [next(p["name"] for p in DATA["processes"] if p["id"] == target) for target in process["downstream"]]
DATA["relationships"] = [{"from_id": p["id"], "to_id": target, "type": "conceptual-process-dependency", "evidence_status": "public-engineering-source", "source": p["evidence"][0]["url"]} for p in DATA["processes"] for target in p["downstream"]]
# v0.4: individually sourced facilities supporting one Southern California reference path.
FACILITY_EVIDENCE = [
    {"id": "jpl-25ft", "organization_id": "nasa-jpl", "name": "NASA JPL 25-Foot Space Simulator", "location_label": "La Cañada Flintridge, CA", "latitude": 34.2014, "longitude": -118.1718, "location_precision": "address-derived", "verification_status": "official-address-and-facility-source", "facility_type": "environmental-test", "capability_ids": ["environmental-test"], "process_ids": ["environmental-test"], "products_services": ["thermal-vacuum, acoustic, vibration and EMI/EMC testing described in the cited JPL account"], "qualification_evidence": "JPL reports spacecraft environmental testing at the facility; mission-specific qualification basis remains unknown.", "source": "https://www.jpl.nasa.gov/images/pia26708-voyager-technologies-griffin-1-completes-environmental-testing-at-nasa-jpl/", "source_date": "2026-10-12", "evidence_classification": "observed", "confidence": "high", "last_verified": "2026-10-28", "unknowns": ["external customer availability", "schedule", "test configuration", "capacity", "commercial terms"]},
    {"id": "jpl-ep-lab", "organization_id": "nasa-jpl", "name": "NASA JPL Electric Propulsion Laboratory", "location_label": "La Cañada Flintridge, CA", "latitude": 34.2014, "longitude": -118.1718, "location_precision": "address-derived", "verification_status": "official-address-and-facility-source", "facility_type": "propulsion-test", "capability_ids": ["propulsion", "environmental-test"], "process_ids": ["propulsion", "environmental-test"], "products_services": ["vacuum, thermal-vacuum, vibration and shock test capability for electric propulsion work"], "qualification_evidence": "Public facility description documents capability; it does not establish availability for a particular mission.", "source": "https://www.jpl.nasa.gov/go/epl/capabilities/facilities/", "source_date": "2026-10-28", "evidence_classification": "observed", "confidence": "high", "last_verified": "2026-10-28", "unknowns": ["mission applicability", "test slot availability", "capacity", "customer access"]},
    {"id": "vandenberg-sld30", "organization_id": "us-space-force-sld30", "name": "Vandenberg Space Force Base / Space Launch Delta 30", "location_label": "Vandenberg SFB, CA", "latitude": 34.742, "longitude": -120.572, "location_precision": "base-centroid", "verification_status": "official-installation-source", "facility_type": "launch-infrastructure", "capability_ids": ["launch-integration", "launch-campaign"], "process_ids": ["launch-integration", "launch-campaign"], "products_services": ["West Coast spaceport and test-range support for launch operations"], "qualification_evidence": "Public Space Force description documents range and installation role; it does not establish access for any specific payload.", "source": "https://www.ssc.spaceforce.mil/Program-Offices/SPACE-ACCESS", "source_date": "2026-10-28", "evidence_classification": "observed", "confidence": "high", "last_verified": "2026-10-28", "unknowns": ["launch-provider contract", "payload acceptance", "range approval", "campaign schedule", "available launch opportunity"]},
]
FACILITY_EVIDENCE = json.loads((BASE / "data" / "website" / "facilities.json").read_text(encoding="utf-8"))["facilities"]
DATA["organizations"] = [{"id": c["id"], "name": c["name"], "source": c["source"], "classification": c["evidence_status"]} for c in DATA["companies"]]
DATA["facilities"].extend(FACILITY_EVIDENCE)
for facility in FACILITY_EVIDENCE:
    DATA["relationships"].append({"from_id": facility["organization_id"], "to_id": facility["id"], "type": "organization-operates-facility", "evidence_status": "observed", "source": facility["source"]})
    for capability in facility["capability_ids"]:
        DATA["relationships"].append({"from_id": facility["id"], "to_id": capability, "type": "facility-possesses-documented-capability", "evidence_status": "observed", "source": facility["source"]})
    for process_id in facility["process_ids"]:
        DATA["relationships"].append({"from_id": facility["id"], "to_id": process_id, "type": "facility-supports-industrial-process", "evidence_status": "observed", "source": facility["source"]})
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_PER_HOUR = int(os.getenv("ASK_MAX_PER_HOUR", "24"))
CACHE_TTL = int(os.getenv("ASK_CACHE_SECONDS", "21600"))
CACHE: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
REQUESTS: dict[str, deque[float]] = defaultdict(deque)
STOP = {"the", "what", "which", "could", "would", "from", "about", "where", "companies", "there", "that", "with", "have", "this", "are", "for", "who", "and", "does", "can", "how", "our", "into", "some", "a", "an", "in", "of", "to", "is", "it"}
SYNTHESIS_MARKERS = {"compare", "tradeoff", "prioritize", "scenario", "synthesis", "why", "strategy", "recommend", "risk", "bottleneck", "gap", "across"}
app = FastAPI(title="Space Industrial Base Atlas", version="0.9.0")

ORGANIZATION_IDS = {o["id"] for o in DATA["organizations"]}
FACILITY_IDS = {f["id"] for f in DATA["facilities"]}
PROCESS_IDS = {p["id"] for p in DATA["processes"]}
PROGRAM_IDS = {p["id"] for p in DATA["programs"]}
SOURCE_URLS = ({url for company in DATA["companies"] for url in company["source_urls"]}
               | {f["source"] for f in DATA["facilities"]}
               | {program["source_url"] for program in DATA["programs"]}
               | {source["url"] for source in SOURCES.values()})
EVIDENCE_LIMITATIONS = DATA["limitations"] if isinstance(DATA["limitations"], list) else [DATA["limitations"]]


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1200)
    stage: Optional[str] = None
    process_id: Optional[str] = None
    history: list[ConversationTurn] = Field(default_factory=list, max_length=6)


class Citation(BaseModel):
    label: str = Field(min_length=1, max_length=180)
    url: str = Field(min_length=8, max_length=1000)
    evidence_classification: Literal["observed", "analytical", "conceptual"] = "observed"


class InterfaceAction(BaseModel):
    action: Literal["highlight_facilities", "select_processes", "filter_organizations", "filter_programs", "open_records"]
    label: str = Field(min_length=1, max_length=120)
    target_ids: list[str] = Field(default_factory=list, max_length=20)


class AnalysisRequirement(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    why_it_matters: str = Field(min_length=1, max_length=500)
    process_ids: list[str] = Field(default_factory=list, max_length=14)


class CoverageSignal(BaseModel):
    process_id: str = Field(min_length=1, max_length=80)
    process_name: str = Field(min_length=1, max_length=180)
    organization_count: int = Field(ge=0)
    facility_count: int = Field(ge=0)
    dossier_count: int = Field(ge=0)
    evidence_note: str = Field(min_length=1, max_length=300)


class AnalysisWorkspace(BaseModel):
    interpreted_objective: str = ""
    perspective: Literal["builder", "ecosystem", "mixed"] = "mixed"
    requirements: list[AnalysisRequirement] = Field(default_factory=list, max_length=12)
    coverage: list[CoverageSignal] = Field(default_factory=list, max_length=14)
    next_steps: list[str] = Field(default_factory=list, max_length=10)
    evidence_note: str = "Counts describe current Atlas documentation, not market capacity or supply adequacy."


class AssistantResponse(BaseModel):
    answer_text: str = Field(min_length=1, max_length=5000)
    citations: list[Citation] = Field(default_factory=list, max_length=12)
    organization_ids: list[str] = Field(default_factory=list, max_length=20)
    facility_ids: list[str] = Field(default_factory=list, max_length=20)
    process_ids: list[str] = Field(default_factory=list, max_length=20)
    program_ids: list[str] = Field(default_factory=list, max_length=20)
    suggested_actions: list[InterfaceAction] = Field(default_factory=list, max_length=8)
    unknowns: list[str] = Field(default_factory=list, max_length=20)
    evidence_limitations: list[str] = Field(default_factory=list, max_length=20)
    mode: str = Field(min_length=1, max_length=80)
    analysis: AnalysisWorkspace = Field(default_factory=AnalysisWorkspace)


def terms(text: str) -> set[str]:
    aliases = {"composites": "composite", "machined": "machining", "manufactures": "manufacturing", "manufacturers": "manufacturing", "suppliers": "supplier", "spacecraft": "spacecraft", "satellites": "satellite"}
    return {aliases.get(word, word) for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in STOP}


def score(company: dict[str, Any], words: set[str], stage: Optional[str]) -> int:
    name, place = company["name"].lower(), f"{company['city']} {company['county']}".lower()
    capability = " ".join(company["capabilities"]).lower()
    context = f"{company['sector']} {company['industry_role']} {company['description']} {' '.join(company['stages'])}".lower()
    return sum((5 if word in capability else 3 if word in name else 2 if word in place else 1) for word in words if word in f"{name} {place} {capability} {context}") + (4 if stage and stage in company["stages"] else 0)


def matches(question: str, stage: Optional[str]) -> list[dict[str, Any]]:
    words, q = terms(question), question.lower()
    county_names = ["Los Angeles", "Orange", "San Diego", "Ventura", "Riverside", "San Bernardino", "Santa Barbara"]
    if any(phrase in q for phrase in ("near los angeles", "around los angeles")):
        requested_counties = ["Los Angeles", "Orange", "Ventura"]
    else:
        requested_counties = [county for county in county_names if county.lower() in q]
    pool = [c for c in DATA["companies"] if not requested_counties or c["county"] in requested_counties]
    ranked = sorted(pool, key=lambda c: (-score(c, words, stage), c["name"]))
    relevant = [c for c in ranked if score(c, words, stage) > 0]
    if not relevant and stage:
        relevant = [c for c in ranked if stage in c["stages"]]
    capability_coverage = []
    for word in sorted(words):
        candidates = [c for c in ranked if word in " ".join(c["capabilities"]).lower()]
        if candidates:
            capability_coverage.append(candidates[0])
    return list({c["id"]: c for c in capability_coverage + relevant}.values())[:8]


def citation(label: str, url: str, classification: str = "observed") -> dict[str, str]:
    return {"label": label, "url": url, "evidence_classification": classification}


def action(kind: str, label: str, target_ids: list[str]) -> dict[str, Any]:
    return {"action": kind, "label": label, "target_ids": target_ids}


def coverage_signal(process_id: str) -> dict[str, Any]:
    process = process_by_id(process_id)
    organizations = [c for c in DATA["companies"] if process_id in c.get("process_ids", [])]
    facilities = [f for f in DATA["facilities"] if process_id in f.get("process_ids", [])]
    dossiers = [c for c in organizations if c.get("profile_level") == "deep"]
    official = sum(c.get("evidence_status") == "official_current" for c in organizations)
    return {
        "process_id": process_id,
        "process_name": process["name"] if process else process_id,
        "organization_count": len(organizations),
        "facility_count": len(facilities),
        "dossier_count": len(dossiers),
        "evidence_note": f"{official} organization records are official/current; {len(facilities)} facilities are individually sourced.",
    }


def build_analysis(question: str, response: dict[str, Any]) -> dict[str, Any]:
    q = question.lower()
    ecosystem = any(term in q for term in ("well represented", "coverage", "evidence too weak", "weak evidence", "ecosystem", "region", "locally"))
    perspective = "ecosystem" if ecosystem else "builder"
    objective = question.strip().rstrip("?")
    process_ids = response.get("process_ids", [])
    requirements = []
    for process_id in process_ids[:8]:
        process = process_by_id(process_id)
        if process:
            requirements.append({
                "name": process["name"],
                "why_it_matters": process["purpose"],
                "process_ids": [process_id],
            })
    next_steps = []
    if response.get("facility_ids"):
        next_steps.append("Confirm customer access, hardware envelope, test level, schedule, and commercial terms directly with candidate facilities.")
    if response.get("organization_ids"):
        next_steps.append("Review the cited public description, then verify the exact capability, qualification basis, capacity, and availability with each candidate.")
    if process_ids:
        next_steps.append("Use the highlighted production stages to identify interfaces, evidence requirements, and downstream dependencies.")
    if ecosystem:
        next_steps.append("Prioritize validation where records rely on secondary indexes or where no individually sourced facility is documented.")
    if any(term in q for term in ("thermal-vacuum", "thermal vacuum")):
        next_steps = [
            "Define the hardware envelope, temperature and pressure profiles, instrumentation, cleanliness constraints, and whether this is qualification or acceptance testing.",
            "Review the sourced facility record, then confirm customer access, chamber fit, schedule, configuration, and commercial terms directly with the operator.",
            "Prepare the test plan, success criteria, configuration record, and required test-report evidence before reserving a slot.",
        ]
    elif "communications payload" in q:
        next_steps = [
            "Freeze the payload's frequency band, link budget, antenna, power, data, mechanical, thermal, and ground-segment interfaces.",
            "Define functional, EMC/RF, environmental, and acceptance evidence required for payload and spacecraft integration.",
            "Use the highlighted records to create a verification shortlist, then confirm exact capability, qualification basis, access, capacity, and schedule with each candidate.",
        ]
    elif any(term in q for term in ("completed assembly", "assembly is complete", "finished assembly", "what comes next")):
        next_steps = [
            "Freeze the as-built configuration and close outstanding functional, interface, workmanship, and acceptance records.",
            "Confirm the mission-specific environmental verification matrix, including qualification-versus-acceptance levels and retest rules.",
            "Align transport, launch-provider interface approval, range documentation, campaign schedule, and operational-readiness evidence.",
        ]
    elif "rf systems" in q or "rf components" in q:
        next_steps = [
            "Specify the RF function, frequency band, performance, environmental, interface, and qualification requirements before shortlisting candidates.",
            "Inspect each cited record and separate first-party evidence from directory-tier discovery leads.",
            "Confirm product fit, flight heritage or qualification basis, capacity, lead time, and procurement availability directly with candidates.",
        ]
    return {
        "interpreted_objective": objective,
        "perspective": perspective,
        "requirements": requirements,
        "coverage": [coverage_signal(pid) for pid in process_ids],
        "next_steps": next_steps[:6],
        "evidence_note": "Counts describe current Atlas documentation, not market capacity, supplier availability, or regional supply adequacy.",
    }


def deterministic_answer(found: list[dict[str, Any]], stage: Optional[str]) -> dict[str, Any]:
    stage_name = next((s["name"] for s in DATA["stages"] if s["id"] == stage), None)
    if not found:
        return coverage_gap_answer()
    lead = f"Registry matches for {stage_name}" if stage_name else "The Atlas found public-description matches"
    listings = "; ".join(f"{c['name']} ({c['city']}, {c['county']}; {', '.join(c['capabilities'][:3])}; evidence: {c['evidence_status']}; profile: {c['profile_level']})" for c in found[:5])
    ids = [c["id"] for c in found]
    process_ids = list(dict.fromkeys(process_id for company in found for process_id in company["process_ids"]))[:6]
    return {
        "answer_text": f"{lead}: {listings}. Inclusion is based on the cited public description or directory capability tags, and an individual candidate may satisfy only part of a multi-attribute request. Directory-tier rows are preliminary candidates; none of these results establishes a supplier relationship, availability, capacity, pricing, or mission qualification.",
        "citations": [citation(c["name"], c["source"]) for c in found[:5]],
        "organization_ids": ids, "facility_ids": [], "process_ids": process_ids, "program_ids": [],
        "suggested_actions": [action("filter_organizations", "Inspect candidate organizations", ids)] + ([action("select_processes", "Connect matches to production processes", process_ids)] if process_ids else []) + [action("open_records", "Open related records", ids)],
        "unknowns": ["complete match to every requested material and process", "supplier relationship", "current operating status for directory-only rows", "flight qualification", "capacity and availability", "lead time"],
        "evidence_limitations": EVIDENCE_LIMITATIONS, "mode": "deterministic-registry",
    }


def process_by_id(process_id: Optional[str]) -> Optional[dict[str, Any]]:
    return next((p for p in DATA.get("processes", []) if p["id"] == process_id), None)


def process_answer(processes: list[dict[str, Any]]) -> dict[str, Any]:
    process_ids = [p["id"] for p in processes]
    capability_ids = {cap for p in processes for cap in p.get("capability_ids", [])}
    candidates = [c for c in DATA["companies"] if set(c.get("capability_ids", [])) & capability_ids][:8]
    facilities = [f for f in DATA["facilities"] if set(f.get("process_ids", [])) & set(process_ids)]
    process_summary = " → ".join(p["name"] for p in processes)
    purpose = " ".join(p["purpose"] for p in processes)
    source_rows = {e["url"]: e for p in processes for e in p.get("evidence", [])}
    organization_ids = list(dict.fromkeys([f["organization_id"] for f in facilities] + [c["id"] for c in candidates]))[:20]
    return {
        "answer_text": f"The reference pathway is {process_summary}. {purpose} This is a conceptual engineering sequence, not a claim about a specific program's commercial flow.",
        "citations": ([citation(e["title"], e["url"], "conceptual") for e in source_rows.values()] + [citation(f["name"], f["source"]) for f in facilities])[:12],
        "organization_ids": organization_ids, "facility_ids": [f["id"] for f in facilities][:20], "process_ids": process_ids, "program_ids": [],
        "suggested_actions": [action("select_processes", "Trace the production pathway", process_ids)] + ([action("highlight_facilities", "Show documented facilities", [f["id"] for f in facilities])] if facilities else []) + ([action("filter_organizations", "Inspect capability candidates", [c["id"] for c in candidates])] if candidates else []),
        "unknowns": sorted({gap for p in processes for gap in p["evidence_gaps"]})[:20],
        "evidence_limitations": EVIDENCE_LIMITATIONS, "mode": "deterministic-process",
    }


def ecosystem_coverage_answer(weak_only: bool = False) -> dict[str, Any]:
    signals = [coverage_signal(p["id"]) for p in DATA["processes"]]
    if weak_only:
        ranked = sorted(signals, key=lambda row: (row["facility_count"] > 0, row["dossier_count"], row["organization_count"]))[:6]
        process_ids = [row["process_id"] for row in ranked]
        summary = "; ".join(f"{row['process_name']} ({row['organization_count']} records, {row['dossier_count']} dossiers, {row['facility_count']} sourced facilities)" for row in ranked)
        answer = f"The weakest-documented portions of the current Atlas are: {summary}. This is a documentation-priority signal, not proof that the capability is absent locally."
        mode = "deterministic-evidence-gap"
    else:
        ranked = sorted(signals, key=lambda row: (row["organization_count"], row["dossier_count"], row["facility_count"]), reverse=True)[:6]
        process_ids = [row["process_id"] for row in ranked]
        summary = "; ".join(f"{row['process_name']} ({row['organization_count']} records, {row['dossier_count']} dossiers, {row['facility_count']} sourced facilities)" for row in ranked)
        answer = f"The most documented portions of the current Atlas are: {summary}. These counts measure evidence coverage in this dataset—not local capacity, supplier availability, or supply-chain adequacy."
        mode = "deterministic-ecosystem-coverage"
    return {
        "answer_text": answer,
        "citations": [citation(source["title"], source["url"], "conceptual") for source in SOURCES.values()],
        "organization_ids": [], "facility_ids": [], "process_ids": process_ids, "program_ids": [],
        "suggested_actions": [action("select_processes", "Inspect these pathway stages", process_ids)],
        "unknowns": ["unlisted organizations and facilities", "current capacity and availability", "actual supply relationships", "whether sparse documentation indicates a real regional gap"],
        "evidence_limitations": EVIDENCE_LIMITATIONS,
        "mode": mode,
    }


def coverage_gap_answer(programs: bool = False) -> dict[str, Any]:
    topic = "startup-support program" if programs else "requested topic"
    return {
        "answer_text": f"The Atlas does not yet contain a documented {topic} dataset, so it cannot provide a grounded recommendation from current records. Add authoritative program or domain sources before treating results as coverage.",
        "citations": [], "organization_ids": [], "facility_ids": [], "process_ids": [], "program_ids": [], "suggested_actions": [],
        "unknowns": [f"authoritative {topic} records", "eligibility and geographic restrictions", "current availability and deadlines"],
        "evidence_limitations": EVIDENCE_LIMITATIONS, "mode": "deterministic-coverage-gap",
    }


def facility_answer(found: list[dict[str, Any]]) -> dict[str, Any]:
    found = found[:12]
    facility_ids = [f["id"] for f in found]
    process_ids = list(dict.fromkeys(pid for f in found for pid in f.get("process_ids", [])))
    organization_ids = list(dict.fromkeys(f["organization_id"] for f in found))
    listings = "; ".join(f"{f['name']} ({f['location_label']}: {', '.join(f['products_services'])})" for f in found)
    return {
        "answer_text": f"Documented facility matches: {listings}. The cited capability does not establish access, schedule, capacity, pricing, or mission fit.",
        "citations": [citation(f["name"], f["source"]) for f in found],
        "organization_ids": organization_ids, "facility_ids": facility_ids, "process_ids": process_ids, "program_ids": [],
        "suggested_actions": [action("highlight_facilities", "Highlight documented facilities", facility_ids), action("select_processes", "Inspect applicable processes", process_ids), action("open_records", "Inspect facility records", facility_ids)],
        "unknowns": sorted({gap for f in found for gap in f.get("unknowns", [])})[:20],
        "evidence_limitations": EVIDENCE_LIMITATIONS, "mode": "deterministic-facility",
    }


def relevant_processes(question: str) -> list[dict[str, Any]]:
    q, words = question.lower(), terms(question)
    if "communications payload" in q or ("payload" in q and any(term in q for term in ("rf", "communication", "communications"))):
        ids = ["materials", "comms", "payload", "harness", "functional-test", "integration", "environmental-test"]
        return [process_by_id(pid) for pid in ids if process_by_id(pid)]
    if any(term in q for term in ("completed assembly", "assembly is complete", "finished assembly", "after assembly", "what comes next")):
        ids = ["functional-test", "integration", "environmental-test", "launch-integration", "launch-campaign", "operations"]
        return [process_by_id(pid) for pid in ids if process_by_id(pid)]
    if ("assembly" in q or "integration" in q) and "launch" in q:
        ids = ["integration", "environmental-test", "launch-integration", "launch-campaign"]
        return [process_by_id(pid) for pid in ids if process_by_id(pid)]
    ranked = []
    for process in DATA["processes"]:
        hay = " ".join([process["id"], process["name"], process["purpose"], " ".join(process["requirements"])]).lower()
        value = sum(1 for word in words if word in hay)
        if value:
            ranked.append((value, process))
    return [p for _, p in sorted(ranked, key=lambda row: -row[0])[:4]]


def relevant_facilities(question: str) -> list[dict[str, Any]]:
    q = question.lower()
    desired: set[str] = set()
    if any(word in q for word in ("test", "testing", "qualification", "thermal", "vacuum", "vibration", "emc")):
        desired.add("environmental-test")
    if "propulsion" in q:
        desired.add("propulsion")
    if "launch" in q or "vandenberg" in q:
        desired.update(("launch-integration", "launch-campaign"))
    facilities = [f for f in DATA["facilities"] if f.get("verification_status")]
    if desired:
        facilities = [f for f in facilities if desired & (set(f.get("capability_ids", [])) | set(f.get("process_ids", [])))]
    if any(term in q for term in ("thermal-vacuum", "thermal vacuum", "vacuum")):
        facilities = [f for f in facilities if any(term in " ".join(f.get("products_services", [])).lower() for term in ("thermal-vacuum", "thermal vacuum", "vacuum"))]
    if "vibration" in q:
        facilities = [f for f in facilities if "vibration" in " ".join(f.get("products_services", [])).lower()]
    if any(term in q for term in ("emc", "emi", "rf test")):
        facilities = [f for f in facilities if any(term in " ".join(f.get("products_services", [])).lower() for term in ("emc", "emi", "rf test"))]
    return facilities


def relevant_programs(question: str) -> list[dict[str, Any]]:
    q, words = question.lower(), terms(question)
    if any(term in q for term in ("connect", "community", "ecosystem", "event")):
        return [program for program in DATA["programs"] if program["category"] == "regional-ecosystem-network"]
    if "tacfi" in q:
        return [program for program in DATA["programs"] if program["id"] == "spacewerx-tacfi-py26-2"]
    if "stratfi" in q:
        return [program for program in DATA["programs"] if program["id"] == "spacewerx-stratfi"]
    if "taba" in q:
        return [program for program in DATA["programs"] if program["id"] == "spacewerx-taba"]
    if "spacewerx" in q:
        return [program for program in DATA["programs"] if program["id"].startswith("spacewerx-") or ("sbir" in q and program["id"] == "americas-seed-fund-sbir-sttr")]
    if "sbir" in q or "sttr" in q:
        ids = {"americas-seed-fund-sbir-sttr", "spacewerx-sbir-sttr"}
        return [program for program in DATA["programs"] if program["id"] in ids]
    ranked: list[tuple[int, dict[str, Any]]] = []
    for program in DATA["programs"]:
        hay = " ".join([
            program["name"], program["provider"], program["category"], program["description"],
            program["geography"], " ".join(program["eligibility"]), program["status_detail"],
        ]).lower()
        value = sum(3 if word in program["name"].lower() else 1 for word in words if word in hay)
        if "spacewerx" in q and "spacewerx" in hay:
            value += 6
        if any(term in q for term in ("startup", "funding", "grant", "support")) and program["category"] != "regional-ecosystem-network":
            value += 2
        if value:
            ranked.append((value, program))
    return [program for _, program in sorted(ranked, key=lambda row: (-row[0], row[1]["name"]))[:8]]


def program_answer(found: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [program["id"] for program in found]
    listings = "; ".join(f"{program['name']} [{program['status']}]: {program['description']} {program['status_detail']}" for program in found[:6])
    return {
        "answer_text": f"Documented support and ecosystem matches: {listings} Status labels describe the official pages as reviewed on 2026-10-29; confirm time-sensitive windows at the cited source before acting.",
        "citations": [citation(program["name"], program["source_url"]) for program in found],
        "organization_ids": [], "facility_ids": [], "process_ids": [], "program_ids": ids,
        "suggested_actions": [action("filter_programs", "Inspect program and ecosystem records", ids), action("open_records", "Open related records", ids)],
        "unknowns": sorted({unknown for program in found for unknown in program["unknowns"]})[:20],
        "evidence_limitations": EVIDENCE_LIMITATIONS + ["Program status and deadlines can change after the recorded review date."],
        "mode": "deterministic-program",
    }


def deterministic_route(payload: AskRequest) -> dict[str, Any]:
    question, q = payload.question.strip(), payload.question.lower()
    if any(term in q for term in ("evidence too weak", "weak evidence", "too weak to know", "where is the evidence", "least documented", "regional bottleneck")):
        return ecosystem_coverage_answer(weak_only=True)
    if any(term in q for term in ("well represented", "best represented", "strongest coverage", "strongest evidence coverage", "coverage by process", "represented locally")):
        return ecosystem_coverage_answer()
    program_intent = any(term in q for term in ("program", "grant", "funding", "accelerator", "spacewerx", "sbir", "sttr", "tacfi", "stratfi", "taba", "rocket fund", "organizations connect", "community", "event"))
    if program_intent:
        programs = relevant_programs(question)
        if programs:
            return program_answer(programs)
        return coverage_gap_answer(programs=True)
    facility_intent = any(term in q for term in ("facility", "facilities", "where can", "where could", "test", "testing", "qualification", "thermal", "vacuum", "launch site", "spaceport"))
    if facility_intent:
        facilities = relevant_facilities(question)
        if facilities:
            response = facility_answer(facilities)
            if any(term in q for term in ("thermal-vacuum", "thermal vacuum", "vacuum", "vibration", "emc", "emi")):
                response["process_ids"] = ["environmental-test"]
                response["suggested_actions"] = [
                    action("highlight_facilities", "Highlight documented facilities", response["facility_ids"]),
                    action("select_processes", "Inspect environmental qualification", ["environmental-test"]),
                    action("open_records", "Inspect facility records", response["facility_ids"]),
                ]
            return response
    follow_up = any(term in q.split() for term in ("it", "this", "that", "requirements", "inputs", "evidence"))
    selected = process_by_id(payload.process_id) if payload.process_id and follow_up else None
    processes = [selected] if selected else relevant_processes(question)
    process_intent = any(term in q for term in ("process", "pathway", "from assembly", "to launch", "dependencies", "qualification flow", "communications payload", "completed assembly", "what comes next"))
    if processes and process_intent:
        return process_answer(processes)
    return deterministic_answer(matches(question, payload.stage), payload.stage)


def validate_response(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate every model or deterministic ID, citation and interface action."""
    parsed = AssistantResponse.model_validate(raw)
    parsed.organization_ids = list(dict.fromkeys(x for x in parsed.organization_ids if x in ORGANIZATION_IDS))
    parsed.facility_ids = list(dict.fromkeys(x for x in parsed.facility_ids if x in FACILITY_IDS))
    parsed.process_ids = list(dict.fromkeys(x for x in parsed.process_ids if x in PROCESS_IDS))
    parsed.program_ids = list(dict.fromkeys(x for x in parsed.program_ids if x in PROGRAM_IDS))
    parsed.citations = [c for c in parsed.citations if c.url in SOURCE_URLS]
    targets = {
        "highlight_facilities": FACILITY_IDS,
        "select_processes": PROCESS_IDS,
        "filter_organizations": ORGANIZATION_IDS,
        "filter_programs": PROGRAM_IDS,
        "open_records": ORGANIZATION_IDS | FACILITY_IDS | PROGRAM_IDS,
    }
    safe_actions = []
    for suggested in parsed.suggested_actions:
        suggested.target_ids = list(dict.fromkeys(x for x in suggested.target_ids if x in targets[suggested.action]))
        if suggested.target_ids:
            safe_actions.append(suggested)
    parsed.suggested_actions = safe_actions
    return parsed.model_dump()


def should_synthesize(question: str) -> bool:
    q = question.lower()
    return any(marker in q for marker in SYNTHESIS_MARKERS) or len(terms(q)) > 13


def take_slot(request: Request) -> bool:
    ip, now = (request.client.host if request.client else "unknown"), time.time()
    q = REQUESTS[ip]
    while q and q[0] <= now - 3600: q.popleft()
    if len(q) >= MAX_PER_HOUR: return False
    q.append(now); return True


async def create_claude_message(system: str, messages: list[dict[str, str]]) -> Any:
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=35.0, max_retries=1)
    return await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=650,
        system=system,
        messages=messages,
    )


DATA["ecosystem_intelligence"] = {
    "label": "Ecosystem intelligence preview",
    "as_of": "2026-10-29",
    "coverage": [coverage_signal(process["id"]) for process in DATA["processes"]],
    "evidence_tiers": dict(sorted({tier: sum(c["evidence_status"] == tier for c in DATA["companies"]) for tier in {c["evidence_status"] for c in DATA["companies"]}}.items())),
    "note": "Coverage metrics describe records in the Atlas, not regional capacity, supplier availability, or proof that an undocumented capability is absent.",
}


@app.get("/")
def homepage(): return FileResponse(BASE / "index.html")


@app.get("/api/data")
def get_data(): return DATA


@app.get("/healthz")
def health(): return {"ok": True, "version": "0.9.0", "organizations": len(DATA["organizations"]), "facilities": len(DATA.get("facilities", [])), "profiles": sum(c["profile_level"] == "deep" for c in DATA["companies"]), "processes": len(DATA.get("processes", [])), "programs": len(DATA["programs"]), "anthropic_configured": bool(ANTHROPIC_API_KEY)}


@app.post("/api/ask")
async def ask(payload: AskRequest, request: Request):
    question = payload.question.strip()
    baseline = validate_response(deterministic_route(payload))
    baseline["analysis"] = build_analysis(question, baseline)
    baseline = validate_response(baseline)
    if not should_synthesize(question) or not ANTHROPIC_API_KEY:
        return baseline
    if not take_slot(request):
        baseline["mode"] = "deterministic-rate-limit"
        return JSONResponse(baseline, status_code=429)
    cache_key = hashlib.sha256(f"{question.lower()}|{payload.process_id or ''}|{ANTHROPIC_MODEL}".encode()).hexdigest()
    cached = CACHE.get(cache_key)
    if cached and cached[0] > time.time():
        response = dict(cached[1]); response["mode"] = "claude-cached"; return response
    context = {"retrieved_response": baseline, "limitations": DATA["limitations"]}
    system = """You are the synthesis layer for an evidence-bound space industrial intelligence system. Use only the supplied retrieved response. Keep observed facts distinct from analytical matches and conceptual process dependencies. Never invent supplier relationships, production capacity, qualification, lead time, backlog, launch contracts, programs, or bottlenecks. Sparse coverage is not proof of a gap. Return JSON only with exactly: {\"answer_text\": string, \"citations\": [{\"label\": string, \"url\": string, \"evidence_classification\": \"observed\"|\"analytical\"|\"conceptual\"}], \"unknowns\": [string]}. Keep the answer under 220 words."""
    conversation = [{"role": turn.role, "content": turn.content} for turn in payload.history]
    conversation.append({"role": "user", "content": f"Question: {question}\n\nRetrieved Atlas context:\n{json.dumps(context, ensure_ascii=False)}"})
    try:
        message = await create_claude_message(system, conversation)
        output_text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
        parsed = json.loads(output_text)
        result = baseline | {
            "answer_text": str(parsed.get("answer_text") or "").strip(),
            "citations": parsed.get("citations", []),
            "unknowns": parsed.get("unknowns", baseline["unknowns"]),
            "mode": "claude-messages",
        }
        result = validate_response(result)
        CACHE[cache_key] = (time.time() + CACHE_TTL, result)
        while len(CACHE) > 128: CACHE.popitem(last=False)
        return result
    except Exception as exc:
        LOGGER.exception("Anthropic synthesis failed (%s): %s", type(exc).__name__, exc)
        baseline["mode"] = "deterministic-api-fallback"
        return JSONResponse(baseline, headers={"X-Atlas-Synthesis-Error": type(exc).__name__})
