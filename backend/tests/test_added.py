"""Offline tests for objects a visitor adds themselves (added.py): required details, the duplicate check,
privacy between visitors, the book, and descriptions written only from what the visitor typed.

Run from backend/:  ../.venv/bin/python -m pytest -q tests
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient                         # noqa: E402
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel   # noqa: E402

import added                                                       # noqa: E402
import agent                                                       # noqa: E402
import books                                                       # noqa: E402
import main                                                        # noqa: E402

client = TestClient(main.app)
ME = {"x-visitor-id": "visitor-me-1234"}
SOMEONE_ELSE = {"x-visitor-id": "visitor-other-5678"}

FORM = {"museum": "yuag", "title": "Blue Harbour at Dusk", "maker": "Jane Example", "date": "1912",
        "type": "Painting", "medium": "Oil on canvas", "label_text": "A small harbour scene in deep blues.",
        "note": "My grandmother's favourite colour"}


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.setattr(added, "ADDED", tmp_path / "added")
    monkeypatch.setattr(books, "BOOKS", tmp_path / "books")
    monkeypatch.setattr(agent, "USAGE_LOG", tmp_path / "usage.jsonl")
    monkeypatch.setattr(agent, "CACHE_PATH", tmp_path / "cache.json")


def scripted_model(outputs: list[dict], seen: list | None = None) -> FunctionModel:
    """Calls get_object_facts first (recording what it returned), then gives each output in turn."""
    state = {"turn": 0}

    def fn(messages, info: AgentInfo) -> ModelResponse:
        returns = [p for m in messages for p in getattr(m, "parts", []) if isinstance(p, ToolReturnPart)]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("get_object_facts", {})])
        if seen is not None and not seen:
            seen.append(returns[0].content)
        out = outputs[min(state["turn"], len(outputs) - 1)]
        state["turn"] += 1
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, out)])
    return FunctionModel(fn)


def create(form=FORM, headers=ME, confirm=True):
    return client.post("/api/added", json={**form, "confirm_new": confirm}, headers=headers)


def test_required_details():
    for missing in ("museum", "title", "maker", "date", "type"):
        r = create({**FORM, missing: "  "})
        assert r.status_code == 422, missing
    assert create({**FORM, "museum": "louvre"}).status_code == 422          # only Yale's museums
    assert client.post("/api/added", json=FORM).status_code == 400          # no visitor ID, no private store


def test_existing_object_is_suggested_first():
    r = create({**FORM, "museum": "musical_instruments", "title": "Oboe", "maker": "Thomas Cahusac"},
               confirm=False).json()
    assert r["status"] == "possible_duplicates"
    assert r["candidates"][0]["title"] == "Oboe" and "Cahusac" in r["candidates"][0]["maker"]
    assert added.list_added(ME["x-visitor-id"]) == []                      # nothing saved yet
    assert create(confirm=False).json()["status"] == "created"             # a new title goes straight in


def test_added_object_is_in_my_book_and_private():
    r = create().json()
    oid = r["object"]["id"]
    assert r["book"] == [oid] and r["object"]["added_by_visitor"]
    d = client.get(f"/api/objects/{oid}", headers=ME).json()
    assert d["maker"] == "Jane Example" and d["visitor_note"] == FORM["note"] and d["rights"] == added.SOURCE
    assert client.get("/api/book", headers=ME).json()["ids"] == [oid]
    # another visitor can't see it, read its page, or put it in their book
    assert client.get(f"/api/objects/{oid}", headers=SOMEONE_ELSE).status_code == 404
    assert client.get(f"/api/objects/{oid}/blurb", headers=SOMEONE_ELSE).status_code == 404
    assert client.get("/api/added", headers=SOMEONE_ELSE).json() == []
    assert client.put("/api/book", json={"ids": [oid]}, headers=SOMEONE_ELSE).json()["ids"] == []
    # never in browsing or search
    assert client.get("/api/objects", params={"q": "Blue Harbour"}).json()["total"] == 0


def test_delete_removes_it_from_the_book():
    oid = create().json()["object"]["id"]
    assert client.delete(f"/api/added/{oid}", headers=SOMEONE_ELSE).status_code == 404
    assert client.delete(f"/api/added/{oid}", headers=ME).json()["book"] == []
    assert client.get(f"/api/objects/{oid}", headers=ME).status_code == 404


def test_description_uses_only_what_the_visitor_typed():
    oid = create().json()["object"]["id"]
    seen: list = []
    page = {"headline": "A harbour in deep blues",
            "blurb": "Jane Example painted this small harbour scene in 1912, in oil on canvas. The label describes it "
                     "as a harbour in deep blues. It belongs to the Yale University Art Gallery.",
            "look_closer": None, "facts_used": ["title", "maker", "date", "medium", "wall_label_text"]}
    b = asyncio.run(agent.get_added_blurb(main.catalog, ME["x-visitor-id"], oid, model=scripted_model([page], seen)))
    assert b.source == "ai" and b.headline == page["headline"]
    assert seen[0]["wall_label_text"] == FORM["label_text"]
    assert "note" not in seen[0] and FORM["note"] not in str(seen[0])       # the personal note isn't sent
    assert added.get(ME["x-visitor-id"], oid)["blurb"]["blurb"] == page["blurb"]   # kept with the object
    again = asyncio.run(agent.get_added_blurb(main.catalog, ME["x-visitor-id"], oid, model=scripted_model([])))
    assert again.source == "cache"
    assert not agent.CACHE_PATH.exists()                                    # not in the shared, committed cache


def test_invented_fact_is_sent_back_for_added_objects():
    oid = create().json()["object"]["id"]
    bad = {"headline": "A harbour", "blurb": "Jane Example painted this harbour in 1912 after a trip to Brittany in "
           "1909, in oil on canvas, as a small scene in deep blues for the Yale University Art Gallery.",
           "look_closer": None, "facts_used": ["title"]}
    good = {**bad, "blurb": "Jane Example painted this harbour in 1912, in oil on canvas: a small scene in deep "
            "blues, now part of the Yale University Art Gallery's collection of paintings."}
    b = asyncio.run(agent.get_added_blurb(main.catalog, ME["x-visitor-id"], oid, model=scripted_model([bad, good])))
    assert b.source == "ai" and "1909" not in b.blurb


def test_editing_details_rewrites_the_description():
    oid = create().json()["object"]["id"]
    page = {"headline": "A harbour in deep blues", "blurb": " ".join(["Jane Example painted this in 1912."] * 5),
            "look_closer": None, "facts_used": ["maker"]}
    asyncio.run(agent.get_added_blurb(main.catalog, ME["x-visitor-id"], oid, model=scripted_model([page])))
    r = client.put(f"/api/added/{oid}", json={**FORM, "date": "ca. 1915"}, headers=ME)
    assert r.status_code == 200 and r.json()["object"]["date"] == "ca. 1915"
    new = {**page, "blurb": " ".join(["Jane Example painted this around 1915."] * 5)}
    b = asyncio.run(agent.get_added_blurb(main.catalog, ME["x-visitor-id"], oid, model=scripted_model([new])))
    assert b.source == "ai" and "1915" in b.blurb


def test_talk_about_the_details_is_sent_back():
    oid = create().json()["object"]["id"]
    meta = {"headline": "A harbour in deep blues", "blurb": "Jane Example painted Blue Harbour at Dusk in 1912, in oil "
            "on canvas, for the Yale University Art Gallery. The given details say nothing more about the scene.",
            "look_closer": None, "facts_used": ["title"]}
    good = {**meta, "blurb": "Jane Example painted Blue Harbour at Dusk in 1912, in oil on canvas: a small harbour "
            "scene in deep blues, now at the Yale University Art Gallery."}
    b = asyncio.run(agent.get_added_blurb(main.catalog, ME["x-visitor-id"], oid, model=scripted_model([meta, good])))
    assert b.source == "ai" and "details" not in b.blurb
