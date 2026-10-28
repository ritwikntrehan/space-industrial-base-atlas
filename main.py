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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
MAX_PER_HOUR = int(os.getenv("ASK_MAX_PER_HOUR", "24"))
CACHE_TTL = int(os.getenv("ASK_CACHE_SECONDS", "21600"))
CACHE: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
REQUESTS: dict[str, deque[float]] = defaultdict(deque)
STOP = {"the", "what", "which", "could", "would", "from", "about", "where", "companies", "there", "that", "with", "have", "this", "are", "for", "who", "and", "does", "can", "how", "our", "into", "some", "a", "an", "in", "of", "to", "is", "it"}
SYNTHESIS_MARKERS = {"compare", "tradeoff", "prioritize", "scenario", "synthesis", "why", "strategy", "recommend", "risk", "bottleneck", "gap", "across"}
app = FastAPI(title="Space Industrial Base Atlas", version="0.2.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1200)
    stage: Optional[str] = None


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
def health(): return {"ok": True, "version": "0.2.0", "companies": len(DATA["companies"]), "stages": len(DATA["stages"]), "openai_configured": bool(OPENAI_API_KEY)}


@app.post("/api/ask")
async def ask(payload: AskRequest, request: Request):
    question, found = payload.question.strip(), matches(payload.question, payload.stage)
    if not should_synthesize(question) or not OPENAI_API_KEY:
        return deterministic_answer(found, payload.stage)
    if not take_slot(request):
        return JSONResponse(deterministic_answer(found, payload.stage) | {"mode": "deterministic-rate-limit"}, status_code=429)
    cache_key = hashlib.sha256(f"{question.lower()}|{payload.stage or ''}|{OPENAI_MODEL}".encode()).hexdigest()
    cached = CACHE.get(cache_key)
    if cached and cached[0] > time.time():
        response = dict(cached[1]); response["mode"] = "openai-cached"; return response
    context = {"stages": DATA["stages"], "records": found, "limitations": DATA["limitations"]}
    instructions = """You are an evidence-bound industrial-base research assistant. Use only supplied registry data. Separate observed public descriptions, analytical classifications, assumptions, and unknowns. Never invent supplier relationships, production capacity, qualification, lead time, backlog, launch contracts, or bottlenecks. Sparse registry coverage is not proof of a gap. Cite supplied URLs only. Return JSON exactly: {\"answer\": string, \"citations\": [{\"label\": string, \"url\": string}], \"unknowns\": [string]}. Under 180 words."""
    body = {"model": OPENAI_MODEL, "instructions": instructions, "input": f"Question: {question}\n\nRegistry context:\n{json.dumps(context, ensure_ascii=False)}", "max_output_tokens": 550}
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}, json=body)
            response.raise_for_status()
        parsed = json.loads(response.json().get("output_text", ""))
        allowed = {c["source"] for c in found}
        citations = [c for c in parsed.get("citations", []) if isinstance(c, dict) and c.get("url") in allowed][:8]
        result = {"answer": str(parsed.get("answer") or "").strip(), "mode": "openai-responses", "matches": found, "citations": citations, "unknowns": parsed.get("unknowns", []), "limitations": DATA["limitations"]}
        if not result["answer"]: raise ValueError("empty response")
        CACHE[cache_key] = (time.time() + CACHE_TTL, result)
        while len(CACHE) > 128: CACHE.popitem(last=False)
        return result
    except Exception:
        return deterministic_answer(found, payload.stage) | {"mode": "deterministic-api-fallback"}
