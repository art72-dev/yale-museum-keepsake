"""Offline tests: no API key, no network for the agent (a scripted model stands in for gpt-6-luna).

Run from backend/:  ../.venv/bin/python -m pytest -q tests   (or: ../.venv/bin/python tests/test_offline.py)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient                         # noqa: E402
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel   # noqa: E402

import agent                                                       # noqa: E402
import main                                                        # noqa: E402

client = TestClient(main.app)
cat = main.catalog


def scripted_model(outputs: list[dict]) -> FunctionModel:
    """Calls get_object_facts first, then returns each of `outputs` in turn (one per retry)."""
    state = {"turn": 0}

    def fn(messages, info: AgentInfo) -> ModelResponse:
        tool_done = any(isinstance(p, ToolReturnPart) for m in messages for p in getattr(m, "parts", []))
        if not tool_done:
            return ModelResponse(parts=[ToolCallPart("get_object_facts", {})])
        out = outputs[min(state["turn"], len(outputs) - 1)]
        state["turn"] += 1
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, out)])
    return FunctionModel(fn)


def fresh(tmp: Path):
    agent.CACHE_PATH = tmp / "cache.json"
    agent.USAGE_LOG = tmp / "usage.jsonl"


def test_api_lists_and_details():
    assert client.get("/api/health").json()["objects"] > 0
    museums = client.get("/api/museums").json()
    slugs = {m["slug"] for m in museums}
    assert {"yuag", "ycba", "peabody"} <= slugs and "lens_media_lab" not in slugs   # research collections hidden
    page = client.get("/api/objects", params={"museum": "yuag"}).json()
    assert page["total"] == 20 and page["items"][0]["image_usable"]                 # printable first
    oboe = client.get("/api/objects", params={"q": "oboe"}).json()["items"][0]
    d = client.get(f"/api/objects/{oboe['id']}").json()
    assert "Thomas Cahusac" in d["maker"] and d["dimensions"] == "Overall length: 58.4 cm"
    assert d["creators_display"].startswith("Maker: (Made by) Thomas Cahusac")    # the museum's full line, for the page


def test_browsing_mixes_departments_and_folds_lookalikes():
    page = client.get("/api/objects", params={"museum": "peabody"}).json()
    depts = [o["department"] for o in page["items"][:9]]
    assert len(set(depts)) == len(depts)                               # first round: one per department
    shown_tablets = sum(o["title"].startswith("Tablet") for o in page["items"])
    assert shown_tablets <= 3 and any(h["kind"] == "tablet" for h in page["hidden"])
    every = client.get("/api/objects", params={"museum": "peabody", "department": "Babylonian"}).json()
    assert every["total"] == 21 and every["hidden"] == []                # the department shows them all
    found = client.get("/api/objects", params={"museum": "peabody", "q": "tablet"}).json()
    assert found["total"] >= 19                                         # and search finds them all


def test_flagged_image_is_refused_by_the_server():
    flagged = next(o for o in cat.by_id.values() if o["image_usable"] == "no" and o["thumbnail_url"])
    r = client.get(f"/api/objects/{flagged['id']}/image")
    assert r.status_code == 403, r.text


def test_invented_number_is_sent_back_then_fixed(tmp_path):
    fresh(tmp_path)
    oboe = next(o for o in cat.by_id.values() if o["title"] == "Oboe" and "Cahusac" in o["creators"])
    bad = {"headline": "An oboe from 1752", "facts_used": ["title"],
           "blurb": "Thomas Cahusac Sr. made this oboe in 1752 in London, " + "with ivory rings and brass keys " * 6}
    good = {"headline": "Ivory rings and brass keys", "facts_used": ["title", "maker", "date", "description"],
            "blurb": "The English maker Thomas Cahusac Sr. made this oboe around 1750. " + "It has ivory rings " * 8}
    res = asyncio.run(agent.get_blurb(cat, oboe["id"], model=scripted_model([bad, good])))
    assert res.source == "ai" and "1752" not in res.blurb
    log = [json.loads(line) for line in agent.USAGE_LOG.read_text().splitlines()]
    assert log[-1]["retries"] >= 1                                   # the checker sent it back
    again = asyncio.run(agent.get_blurb(cat, oboe["id"], model=scripted_model([bad])))
    assert again.source == "cache" and again.blurb == res.blurb      # second visitor: no tokens spent


def test_unknown_name_gets_one_retry(tmp_path):
    fresh(tmp_path)
    portrait = next(o for o in cat.by_id.values() if o["title"] == "The Portrait")
    padded = {"headline": "A satirical etching", "facts_used": ["title"],
              "blurb": "George Cruikshank etched this print in 1836. It hangs near works by Hogarth. " + "Fine lines " * 12}
    res = asyncio.run(agent.get_blurb(cat, portrait["id"], model=scripted_model([padded, padded])))
    log = json.loads(agent.USAGE_LOG.read_text().splitlines()[-1])
    assert log["retries"] >= 1 and any("Hogarth" in w for w in log["warnings"])


def test_model_failure_falls_back_to_museum_caption(tmp_path):
    fresh(tmp_path)
    def broken(messages, info):
        raise RuntimeError("model down")
    obj = next(o for o in cat.by_id.values() if o["title"] == "The Portrait")
    res = asyncio.run(agent.get_blurb(cat, obj["id"], model=FunctionModel(broken)))
    assert res.source == "fallback" and "George Cruikshank" in res.blurb and res.note
    assert json.loads(agent.USAGE_LOG.read_text().splitlines()[-1])["outcome"] == "fallback"


def test_daily_budget_stops_ai_calls(tmp_path, monkeypatch):
    fresh(tmp_path)
    monkeypatch.setattr(agent, "DAILY_TOKEN_BUDGET", 0)
    obj = next(iter(cat.by_id.values()))
    res = asyncio.run(agent.get_blurb(cat, obj["id"], model=scripted_model([{}])))
    assert res.source == "fallback" and "budget" in res.note


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(["-q", __file__]))
