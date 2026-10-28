import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app

client = TestClient(app)


def test_health_and_data_contract():
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["version"] == "0.2.0"
    data = client.get("/api/data").json()
    assert len(data["stages"]) == 7
    assert len(data["companies"]) >= 18


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
