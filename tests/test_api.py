import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app

client = TestClient(app)


def test_health_and_data_contract():
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["version"] == "0.3.0"
    data = client.get("/api/data").json()
    assert len(data["stages"]) == 7
    assert len(data["companies"]) >= 18
    assert len(data["facilities"]) == len(data["companies"])
    assert len(data["processes"]) >= 14
    assert all(r["type"] == "conceptual-process-dependency" for r in data["relationships"])


def test_lookup_stays_deterministic_and_cited():
    response = client.post("/api/ask", json={"question": "Which companies support RF components?", "stage": "components"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "deterministic-registry"
    assert payload["citations"]
    assert "not verified supplier relationships" in payload["answer"]


def test_unknown_stage_does_not_break_retrieval():
    response = client.post("/api/ask", json={"question": "Tell me about precision manufacturing", "stage": "not-real"})
    assert response.status_code == 200
    assert response.json()["matches"]


def test_process_lookup_is_deterministic_and_source_linked():
    response = client.post("/api/ask", json={"question": "What inputs are required?", "process_id": "integration"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "deterministic-process"
    assert payload["process"]["relationship_type"] == "conceptual-engineering-dependency"
    assert payload["citations"]
    assert payload["unknowns"]


def test_complex_process_question_without_key_keeps_process_context():
    response = client.post("/api/ask", json={"question": "What evidence would be needed to assess a test facility bottleneck?", "process_id": "environmental-test"})
    assert response.status_code == 200
    assert response.json()["mode"] == "deterministic-process"
    assert response.json()["process"]["id"] == "environmental-test"


def test_responses_api_parses_output_content_and_falls_back(monkeypatch):
    import main

    main.OPENAI_API_KEY = "test-key"
    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            class Response:
                def raise_for_status(self): pass
                def json(self): return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"answer":"Source-bound synthesis.","citations":[],"unknowns":["capacity"]}'}]}]}
            return Response()
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)
    response = client.post("/api/ask", json={"question": "Compare integration and testing tradeoffs across the pathway", "process_id": "integration"})
    assert response.status_code == 200
    assert response.json()["mode"] == "openai-responses"
    main.OPENAI_API_KEY = ""
