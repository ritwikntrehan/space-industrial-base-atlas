import json
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main

client = TestClient(main.app)

RESPONSE_FIELDS = {
    "answer_text", "citations", "organization_ids", "facility_ids", "process_ids",
    "program_ids", "suggested_actions", "unknowns", "evidence_limitations", "mode", "analysis",
}


def ask(question, **extra):
    response = client.post("/api/ask", json={"question": question, **extra})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == RESPONSE_FIELDS
    return payload


def test_health_and_data_contract():
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["version"] == "0.9.0"
    assert health.json()["profiles"] == 25
    assert "anthropic_configured" in health.json()
    assert "openai_configured" not in health.json()
    data = client.get("/api/data").json()
    assert len(data["companies"]) == 250
    assert len(data["processes"]) >= 14
    assert len(data["programs"]) == 7
    assert len([f for f in data["facilities"] if f.get("verification_status")]) == 20
    assert {c["county"] for c in data["companies"]} == {
        "Los Angeles", "Orange", "San Diego", "Ventura", "Riverside", "San Bernardino", "Santa Barbara"
    }


def test_homepage_is_compact_and_suggested_queries_precede_map():
    html = client.get("/").text
    assert "<h1" not in html and "hero-copy" not in html
    assert html.count('class="prompt"') >= 6
    assert "I need thermal-vacuum testing." in html
    assert "Where is the evidence too weak to know whether a capability exists?" in html
    assert "county-filter" in html and "evidence-filter" in html and "leaflet.markercluster" in html
    assert html.index('id="ask"') < html.index('id="map-section"') < html.index('id="process-section"')
    assert 'id="intelligence-section"' in html and 'id="workspace"' in html and 'id="share"' in html
    assert 'id="next-steps"' in html and "View pathway and evidence analysis" in html
    assert html.index('id="next-steps"') < html.index('class="analysis-details"')


def test_six_anchor_questions_share_the_analysis_contract():
    corpus = json.loads((Path(__file__).resolve().parents[1] / "data" / "question_corpus.json").read_text())
    anchors = [row for row in corpus["questions"] if row.get("anchor")]
    assert len(anchors) == 6
    for row in anchors:
        payload = ask(row["question"])
        assert payload["mode"] == row["expected_mode"]
        assert payload["analysis"]["interpreted_objective"]
        assert payload["analysis"]["perspective"] in {"builder", "ecosystem", "mixed"}
        assert "not market capacity" in payload["analysis"]["evidence_note"]
        assert all(process in payload["process_ids"] for process in row.get("expected_processes", []))
        if row.get("requires_organizations"):
            assert payload["organization_ids"]


def test_broad_question_corpus_is_schema_safe_and_evidence_bounded():
    corpus = json.loads((Path(__file__).resolve().parents[1] / "data" / "question_corpus.json").read_text())
    assert len(corpus["questions"]) >= 30
    for row in corpus["questions"]:
        payload = ask(row["question"])
        assert payload["mode"] == row["expected_mode"], row["id"]
        assert payload["answer_text"] and payload["analysis"]["interpreted_objective"]
        assert all(citation["url"] in main.SOURCE_URLS for citation in payload["citations"])
        lower = payload["answer_text"].lower()
        assert all(claim.lower() not in lower for claim in row.get("forbidden_claims", []))


def test_ecosystem_preview_reports_documentation_not_supply_adequacy():
    data = client.get("/api/data").json()
    preview = data["ecosystem_intelligence"]
    assert len(preview["coverage"]) == len(data["processes"])
    assert sum(preview["evidence_tiers"].values()) == len(data["companies"])
    assert "not regional capacity" in preview["note"]


def test_facility_question_returns_citations_ids_and_navigation():
    payload = ask("Where can I test a small satellite?")
    assert payload["mode"] == "deterministic-facility"
    assert "jpl-25ft" in payload["facility_ids"]
    assert "environmental-test" in payload["process_ids"]
    assert payload["citations"]
    assert {a["action"] for a in payload["suggested_actions"]} >= {
        "highlight_facilities", "select_processes", "open_records"
    }
    assert "capacity" in " ".join(payload["unknowns"])


def test_composite_question_filters_registry_without_asserting_supplier_relationship():
    payload = ask("Who manufactures aerospace composites around Los Angeles?")
    assert payload["mode"] == "deterministic-registry"
    assert payload["organization_ids"]
    by_id = {row["id"]: row for row in main.DATA["companies"]}
    assert any("composite" in " ".join(by_id[org_id]["capabilities"]).lower() for org_id in payload["organization_ids"])
    assert "none of these results establishes a supplier relationship" in payload["answer_text"]
    assert any(a["action"] == "filter_organizations" for a in payload["suggested_actions"])


def test_large_directory_builder_queries_are_deterministic_and_evidence_bounded():
    machining = ask("Find precision machining suppliers in Orange County")
    assert machining["mode"] == "deterministic-registry"
    assert machining["organization_ids"]
    assert "preliminary candidates" in machining["answer_text"]
    rf = ask("Which companies manufacture RF components?")
    assert rf["organization_ids"] and rf["citations"]
    san_diego = ask("Show me industrial suppliers in San Diego County")
    assert san_diego["organization_ids"]
    assert all(org_id in main.ORGANIZATION_IDS for org_id in san_diego["organization_ids"])


def test_import_reconciliation_and_evidence_tiers():
    records = main.DATA["companies"]
    assert len(records) == len({row["id"] for row in records}) == 250
    assert sum(row["evidence_status"] == "official_current" for row in records) == 17
    assert sum(row["evidence_status"] == "curated_2026_source_snapshot" for row in records) == 63
    assert sum(row["evidence_status"] == "secondary_index_requires_primary_verification" for row in records) == 170
    assert all(row["source_urls"] and row["unknowns"] for row in records)
    profiles = [row for row in records if row["profile_level"] == "deep"]
    assert len(profiles) == 25
    assert all(row["profile"] and row["profile"]["sources"] and row["profile"]["last_reviewed"] for row in profiles)
    assert all("certification_note" in row["profile"] for row in profiles)


def test_supplier_matching_explains_evidence_and_connects_processes():
    payload = ask("I need precision-machined titanium components near Los Angeles")
    assert payload["organization_ids"] and payload["process_ids"]
    assert "SOCAL-laube-titanium-mill-products" in payload["organization_ids"]
    assert "evidence:" in payload["answer_text"] and "profile:" in payload["answer_text"]
    assert "may satisfy only part" in payload["answer_text"]
    assert any(action["action"] == "select_processes" for action in payload["suggested_actions"])
    assert "capacity and availability" in payload["unknowns"]


def test_assembly_to_launch_question_selects_complete_relevant_path():
    payload = ask("How does a satellite get from assembly to launch?")
    assert payload["process_ids"] == [
        "integration", "environmental-test", "launch-integration", "launch-campaign"
    ]
    assert any(a["action"] == "select_processes" for a in payload["suggested_actions"])
    assert any(c["evidence_classification"] == "conceptual" for c in payload["citations"])


def test_program_question_returns_governed_records_and_actions():
    payload = ask("What programs might support my space startup?")
    assert payload["mode"] == "deterministic-program"
    assert not payload["organization_ids"]
    assert payload["program_ids"]
    assert payload["citations"]
    assert any(a["action"] == "filter_programs" for a in payload["suggested_actions"])
    assert "confirm time-sensitive windows" in payload["answer_text"]


def test_spacewerx_query_is_deterministic_and_does_not_claim_every_path_is_open():
    payload = ask("Where can I find SpaceWERX or SBIR opportunities?")
    assert payload["mode"] == "deterministic-program"
    assert "spacewerx-sbir-sttr" in payload["program_ids"]
    assert "americas-seed-fund-sbir-sttr" in payload["program_ids"]
    assert len(payload["program_ids"]) == 5
    assert all(c["url"].startswith("https://") for c in payload["citations"])
    assert "recurring" in payload["answer_text"]


def test_regional_connector_question_returns_socal_deep_tech():
    payload = ask("What organizations connect Southern California space companies?")
    assert payload["program_ids"] == ["socal-deep-tech-week"]
    assert "2027" in payload["answer_text"]


def test_selected_process_supports_contextual_follow_up():
    payload = ask(
        "What evidence is missing for this process?",
        process_id="environmental-test",
        history=[
            {"role": "user", "content": "Where can I test a satellite?"},
            {"role": "assistant", "content": "The Atlas found documented test facilities."},
        ],
    )
    assert payload["process_ids"] == ["environmental-test"]
    assert payload["unknowns"]


def test_backend_removes_unrecognized_ids_actions_and_citations():
    raw = {
        "answer_text": "Validated response.",
        "citations": [
            {"label": "NASA", "url": main.SOURCES["nasa-verification"]["url"], "evidence_classification": "conceptual"},
            {"label": "Injected", "url": "https://malicious.invalid", "evidence_classification": "observed"},
        ],
        "organization_ids": ["SOCAL-jet-propulsion-laboratory", "invented-org"],
        "facility_ids": ["jpl-25ft", "invented-facility"],
        "process_ids": ["integration", "invented-process"],
        "program_ids": ["spacewerx-sbir-sttr", "invented-program"],
        "suggested_actions": [
            {"action": "highlight_facilities", "label": "Show", "target_ids": ["jpl-25ft", "SOCAL-jet-propulsion-laboratory", "invented"]},
            {"action": "select_processes", "label": "Bad", "target_ids": ["invented"]},
            {"action": "filter_programs", "label": "Programs", "target_ids": ["spacewerx-sbir-sttr", "invented"]},
        ],
        "unknowns": [], "evidence_limitations": [], "mode": "test",
    }
    safe = main.validate_response(raw)
    assert safe["organization_ids"] == ["SOCAL-jet-propulsion-laboratory"]
    assert safe["facility_ids"] == ["jpl-25ft"]
    assert safe["process_ids"] == ["integration"]
    assert safe["program_ids"] == ["spacewerx-sbir-sttr"]
    assert len(safe["citations"]) == 1
    assert safe["suggested_actions"] == [
        {"action": "highlight_facilities", "label": "Show", "target_ids": ["jpl-25ft"]},
        {"action": "filter_programs", "label": "Programs", "target_ids": ["spacewerx-sbir-sttr"]},
    ]


def test_claude_messages_synthesis_uses_official_sdk_boundary(monkeypatch):
    main.CACHE.clear()
    monkeypatch.setattr(main, "ANTHROPIC_API_KEY", "test-key")

    async def fake_message(system, messages):
        assert "evidence-bound" in system
        assert messages[-1]["role"] == "user"
        content = json.dumps({
            "answer_text": "Source-bound synthesis that preserves the retrieved evidence.",
            "citations": [{
                "label": "NASA Product Verification",
                "url": main.SOURCES["nasa-verification"]["url"],
                "evidence_classification": "conceptual",
            }],
            "unknowns": ["capacity"],
        })
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=content)])

    monkeypatch.setattr(main, "create_claude_message", fake_message)
    payload = ask("Compare integration and testing tradeoffs across the pathway")
    assert payload["mode"] == "claude-messages"
    assert payload["answer_text"].startswith("Source-bound")
    assert payload["citations"][0]["url"] == main.SOURCES["nasa-verification"]["url"]


def test_claude_api_error_falls_back_to_complete_deterministic_schema(monkeypatch):
    main.CACHE.clear()
    monkeypatch.setattr(main, "ANTHROPIC_API_KEY", "test-key")

    async def failed_message(*_args, **_kwargs):
        raise RuntimeError("mock upstream error")

    monkeypatch.setattr(main, "create_claude_message", failed_message)
    payload = ask("Compare integration and testing tradeoffs across the pathway")
    assert payload["mode"] == "deterministic-api-fallback"
    assert payload["answer_text"]
    assert set(payload) == RESPONSE_FIELDS


def test_request_validation_rejects_unbounded_history_and_short_question():
    turns = [{"role": "user", "content": "context"}] * 7
    assert client.post("/api/ask", json={"question": "x"}).status_code == 422
    assert client.post("/api/ask", json={"question": "valid", "history": turns}).status_code == 422


def test_source_manifest_and_program_records_are_governed():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "data" / "source_manifest.json").read_text())
    programs = json.loads((root / "data" / "website" / "programs.json").read_text())["programs"]
    assert len(manifest["sources"]) >= 7
    required_manifest = {
        "dataset_name", "provider", "source_url", "access_method", "coverage",
        "last_publication_date", "last_retrieved_date", "license_or_reuse",
        "update_frequency", "authentication_required", "ingestion_status", "canonical_tables",
    }
    assert all(required_manifest <= source.keys() for source in manifest["sources"])
    assert any(source["id"] == "sam-opportunities-api" and source["authentication_required"] for source in manifest["sources"])
    assert all(program["source_url"].startswith("https://") for program in programs)
    assert all(program["verification_status"] and program["unknowns"] for program in programs)
