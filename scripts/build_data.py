"""Validate curated source records and build canonical and browser-sized datasets."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source" / "programs_seed.json"
CANONICAL = ROOT / "data" / "canonical" / "programs.json"
WEBSITE = ROOT / "data" / "website" / "programs.json"

REQUIRED = {
    "id", "name", "provider", "category", "description", "geography", "eligibility",
    "status", "status_detail", "source_url", "verification_status", "last_reviewed", "unknowns",
}
ALLOWED_STATUS = {"open", "current", "upcoming", "recurring", "historical", "unverified"}


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
    print(f"built {count} program records ({size} website bytes)")
