"""Validate curated source records and build canonical and browser-sized datasets."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source" / "programs_seed.json"
CANONICAL = ROOT / "data" / "canonical" / "programs.json"
WEBSITE = ROOT / "data" / "website" / "programs.json"
IMPORT = ROOT / "data" / "imports" / "socal-industrial-data" / "website" / "demo_250_organizations.json"
BASE_DATA = ROOT / "data.json"
ORG_CANONICAL = ROOT / "data" / "canonical" / "organizations.json"
ORG_WEBSITE = ROOT / "data" / "website" / "organizations.json"
CROSSWALK = ROOT / "data" / "canonical" / "organization_id_crosswalk.json"
FACILITY_IMPORT = ROOT / "data" / "imports" / "socal-industrial-data" / "website" / "verified_facilities.json"
FACILITY_WEBSITE = ROOT / "data" / "website" / "facilities.json"

REQUIRED = {
    "id", "name", "provider", "category", "description", "geography", "eligibility",
    "status", "status_detail", "source_url", "verification_status", "last_reviewed", "unknowns",
}
ALLOWED_STATUS = {"open", "current", "upcoming", "recurring", "historical", "unverified"}
COUNTIES = {"Los Angeles", "Orange", "San Diego", "Ventura", "Riverside", "San Bernardino", "Santa Barbara"}
EVIDENCE = {"official_current", "curated_2026_source_snapshot", "secondary_index_requires_primary_verification"}
SOURCE_OVERRIDES = {
    "SOCAL-u-s-space-force-space-launch-delta-30": ["https://www.ssc.spaceforce.mil/Program-Offices/SPACE-ACCESS"],
}

PROCESS_TERMS = {
    "materials": ("material", "coating", "ceramic", "composite", "metal", "alloy"),
    "structures": ("structure", "machining", "forming", "fabrication", "composite", "tooling"),
    "avionics": ("avionic", "comput", "sensor", "electronic", "pcb"),
    "power": ("power", "battery", "solar"),
    "comms": ("rf", "radio", "antenna", "communication", "microwave"),
    "propulsion": ("propulsion", "rocket engine", "valve", "fluid", "thruster"),
    "payload": ("payload", "instrument", "optical"),
    "harness": ("wire", "harness", "connector", "cable", "interconnect"),
    "functional-test": ("test", "calibration", "inspection"),
    "integration": ("integration", "assembly", "spacecraft manufacturing", "satellite manufacturing"),
    "environmental-test": ("environmental", "thermal-vacuum", "vibration", "emc", "qualification"),
    "launch-integration": ("launch vehicle", "launch integration", "spaceport"),
    "launch-campaign": ("launch range", "launch site", "launch service"),
    "operations": ("ground system", "mission operation", "space domain"),
}


def normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower().replace("&", "and"))


def process_ids(capabilities: list[str]) -> list[str]:
    hay = " ".join(capabilities).lower()
    return [process_id for process_id, needles in PROCESS_TERMS.items() if any(needle in hay for needle in needles)]


def build_organizations() -> tuple[int, int]:
    imported = json.loads(IMPORT.read_text(encoding="utf-8"))
    existing = json.loads(BASE_DATA.read_text(encoding="utf-8"))["companies"]
    existing_by_name = {normalized_name(row["name"]): row for row in existing}
    records, crosswalk, seen = [], [], set()
    for row in imported:
        if row["county"] not in COUNTIES or row["evidence_status"] not in EVIDENCE:
            raise ValueError(f"{row['id']}: invalid county or evidence tier")
        if not row["source_urls"] or not all(url.startswith("https://") for url in row["source_urls"]):
            raise ValueError(f"{row['id']}: missing HTTPS provenance")
        prior = existing_by_name.get(normalized_name(row["name"]))
        atlas_id = re.sub(r"[^a-z0-9]+", "-", prior["name"].lower()).strip("-") if prior else row["id"]
        if atlas_id in seen:
            raise ValueError(f"duplicate reconciled organization id: {atlas_id}")
        seen.add(atlas_id)
        imported_sources = SOURCE_OVERRIDES.get(row["id"], row["source_urls"])
        sources = list(dict.fromkeys(([prior["source"]] if prior else []) + imported_sources))
        capabilities = list(dict.fromkeys(row["capabilities"]))
        processes = process_ids(capabilities)
        description = prior["description"] if prior else f"Source-reported capabilities: {', '.join(capabilities)}."
        unknowns = ["current operating status", "commercial availability", "capacity", "lead time", "mission-specific qualification"]
        records.append({
            "id": atlas_id, "import_id": row["id"], "name": row["name"], "city": row["city"],
            "county": row["county"], "industry_role": row["industry_role"], "sector": prior["sector"] if prior else row["industry_role"],
            "description": description, "capabilities": capabilities, "process_ids": processes,
            "website": row.get("website") or "", "source_urls": sources, "source": sources[0],
            "evidence_status": row["evidence_status"], "location_precision": row["location_precision"],
            "display_tier": row["atlas_display_tier"], "publication_review_required": bool(row["publication_review_required"]),
            "unknowns": unknowns, "reviewed_on": "2026-10-29",
        })
        crosswalk.append({"import_id": row["id"], "atlas_id": atlas_id, "decision": "merged-existing-authoritative" if prior else "new-selected-import", "matched_name": row["name"]})
    if len(records) != 250 or {row["county"] for row in records} != COUNTIES:
        raise ValueError("selected organization build must contain 250 records across all seven counties")
    canonical = sorted(records, key=lambda row: (row["county"], row["name"]))
    ORG_CANONICAL.write_text(json.dumps({"schema_version": "2.0", "records": canonical}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ORG_WEBSITE.write_text(json.dumps({"schema_version": "2.0", "organizations": canonical}, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    CROSSWALK.write_text(json.dumps({"schema_version": "1.0", "records": crosswalk}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(canonical), ORG_WEBSITE.stat().st_size


def build_facilities() -> tuple[int, int]:
    imported = json.loads(FACILITY_IMPORT.read_text(encoding="utf-8"))
    crosswalk = {row["import_id"]: row["atlas_id"] for row in json.loads(CROSSWALK.read_text(encoding="utf-8"))["records"]}
    records = []
    for row in imported:
        capabilities = [value.strip() for value in row["capabilities"].split(";") if value.strip()]
        records.append({
            "id": row["facility_id"], "organization_id": crosswalk.get(row["organization_id"], row["organization_id"]),
            "name": row["name"], "location_label": ", ".join(filter(None, (row.get("city"), row.get("county")))),
            "street_address": row.get("street_address", ""),
            "latitude": float(row["latitude"]) if row.get("latitude") else None,
            "longitude": float(row["longitude"]) if row.get("longitude") else None,
            "location_precision": row["location_precision"], "verification_status": row["verification_status"],
            "facility_type": row["facility_type"], "capability_ids": process_ids(capabilities),
            "process_ids": process_ids(capabilities), "products_services": capabilities,
            "qualification_evidence": "The cited source documents the site or facility; mission-specific qualification and customer access remain unverified.",
            "source": row["source_url"], "last_verified": row["date_verified"],
            "unknowns": ["customer access", "capacity", "availability", "pricing", "mission-specific qualification"],
        })
    if len(records) != 20 or len({row["id"] for row in records}) != 20:
        raise ValueError("verified facility import must contain 20 unique records")
    FACILITY_WEBSITE.write_text(json.dumps({"schema_version": "2.0", "facilities": records}, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return len(records), FACILITY_WEBSITE.stat().st_size


def validate(record: dict[str, Any]) -> None:
    missing = REQUIRED - record.keys()
    if missing:
        raise ValueError(f"{record.get('id', '<unknown>')}: missing {sorted(missing)}")
    if record["status"] not in ALLOWED_STATUS:
        raise ValueError(f"{record['id']}: unsupported status {record['status']}")
    if not record["source_url"].startswith("https://"):
        raise ValueError(f"{record['id']}: official source must use HTTPS")
    date.fromisoformat(record["last_reviewed"])
    for field in ("opens_on", "closes_on"):
        if record.get(field):
            date.fromisoformat(record[field])
    if not record["eligibility"] or not record["unknowns"]:
        raise ValueError(f"{record['id']}: eligibility and unknowns must be explicit")


def build() -> tuple[int, int]:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = source["records"]
    ids: set[str] = set()
    for record in records:
        validate(record)
        if record["id"] in ids:
            raise ValueError(f"duplicate program id: {record['id']}")
        ids.add(record["id"])
    canonical = sorted(records, key=lambda row: (row["category"], row["name"]))
    website_fields = (
        "id", "name", "provider", "category", "description", "geography", "eligibility",
        "status", "status_detail", "opens_on", "closes_on", "source_url",
        "verification_status", "last_reviewed", "unknowns",
    )
    website = [{key: row.get(key) for key in website_fields} for row in canonical]
    CANONICAL.parent.mkdir(parents=True, exist_ok=True)
    WEBSITE.parent.mkdir(parents=True, exist_ok=True)
    CANONICAL.write_text(json.dumps({"schema_version": "1.0", "records": canonical}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    WEBSITE.write_text(json.dumps({"schema_version": "1.0", "programs": website}, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return len(canonical), WEBSITE.stat().st_size


if __name__ == "__main__":
    count, size = build()
    org_count, org_size = build_organizations()
    facility_count, facility_size = build_facilities()
    print(f"built {count} program records ({size} website bytes)")
    print(f"built {org_count} organization records ({org_size} website bytes)")
    print(f"built {facility_count} facility records ({facility_size} website bytes)")
