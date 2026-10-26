"""Offline tests of the scanner's guards: a scripted model stands in for gpt-6-luna and tries to misbehave.

Run from backend/:  ../.venv/bin/python -m pytest -q tests
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest                                                      # noqa: E402
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel   # noqa: E402

import agent                                                       # noqa: E402
import books                                                       # noqa: E402
import scanner                                                     # noqa: E402
from catalog import Catalog                                        # noqa: E402
from models import BlurbResponse, PhotoReading                     # noqa: E402

cat = Catalog()
VIOLIN = next(o for o in cat.by_id.values() if o["accession_number"] == "4719.1962")
OBOE = next(o for o in cat.by_id.values() if o["title"] == "Oboe" and "Cahusac" in o["creators"])


def script(calls: list[tuple[str, dict]], final: dict) -> FunctionModel:
    """Make the listed tool calls one per turn, then return `final` as the scan result."""
    def fn(messages, info: AgentInfo) -> ModelResponse:
        done = sum(isinstance(p, ToolReturnPart) for m in messages for p in getattr(m, "parts", []))
        if done < len(calls):
            name, args = calls[done]
            return ModelResponse(parts=[ToolCallPart(name, args)])
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, final)])
    return FunctionModel(fn)


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.setattr(books, "BOOKS", tmp_path / "books")
    monkeypatch.setattr(agent, "USAGE_LOG", tmp_path / "usage.jsonl")
    async def fake_blurb(catalog, oid, visitor="x", model=None):
        return BlurbResponse(object_id=oid, headline="h", blurb="b", source="cache", model="test")
    monkeypatch.setattr(agent, "get_blurb", fake_blurb)
    yield
    scanner._model_override = None


def run(model, reading: PhotoReading, visitor="t1"):
    scanner._model_override = model
    async def fake_read(image, media_type, usage):
        return reading
    scanner.read_image = fake_read
    return asyncio.run(scanner.run_scan(cat, b"jpeg", "image/jpeg", visitor))


LABEL = PhotoReading(kind="label", title="Violin, 1/2 size", maker="Gennaro Gagliano", object_number="4719.1962",
                     description="a wall label")
NO_LABEL = PhotoReading(kind="artwork", keywords="musical instrument woodwind wood", description="a wind instrument")


def test_label_with_object_number_is_added():
    r = run(script([("read_photo", {}), ("search_collection", {"object_number": "4719.1962"}),
                    ("write_blurb", {"object_id": VIOLIN["id"]}), ("add_to_book", {"object_id": VIOLIN["id"]})],
                   {"status": "added", "object_id": VIOLIN["id"], "message": "Found it"}), LABEL)
    assert r.status == "added" and r.book == [VIOLIN["id"]] and r.object["id"] == VIOLIN["id"]


def test_lookalike_without_label_is_refused():
    # The model tries to add the oboe from a keyword search: not confident, so the tool refuses.
    r = run(script([("read_photo", {}), ("search_collection", {"keywords": "musical instrument woodwind wood"}),
                    ("add_to_book", {"object_id": OBOE["id"]})],
                   {"status": "added", "object_id": OBOE["id"], "message": "Added the oboe!"}), NO_LABEL)
    assert r.book == [] and r.status == "choose"                 # the false "added" claim is corrected
    assert any(s["summary"].startswith("Refused") for s in r.steps)


def test_object_not_from_search_is_refused():
    r = run(script([("read_photo", {}), ("add_to_book", {"object_id": OBOE["id"]})],
                   {"status": "added", "object_id": OBOE["id"], "message": "Added"}), LABEL)
    assert r.book == [] and r.status != "added"


def test_only_one_object_per_scan():
    # Injection-style behaviour: after a real add, the model tries to add a second object.
    r = run(script([("read_photo", {}), ("search_collection", {"object_number": "4719.1962"}),
                    ("add_to_book", {"object_id": VIOLIN["id"]}),
                    ("search_collection", {"keywords": "musical instrument woodwind"}),
                    ("add_to_book", {"object_id": OBOE["id"]})],
                   {"status": "added", "object_id": VIOLIN["id"], "message": "Added two!"}), LABEL)
    assert r.book == [VIOLIN["id"]]


def test_label_read_but_only_lookalikes_is_not_found():
    unknown = PhotoReading(kind="label", title="Square Saint-Pierre, Paris", maker="Vincent van Gogh",
                           object_number="1958.59", description="a label")
    r = run(script([("read_photo", {}), ("search_collection", {"keywords": "musical instrument woodwind"})],
                   {"status": "choose", "candidate_ids": [OBOE["id"]], "message": "Maybe these?"}), unknown)
    assert r.status == "not_found" and r.candidates == []
