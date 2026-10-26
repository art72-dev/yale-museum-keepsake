"""Yale Museum Keepsake API. Run from backend/:  uvicorn main:app --reload --port 8000

GET /api/health                     data folder, counts, model, whether an API key is set
GET /api/museums                    museums with counts and departments
GET /api/objects                    search/browse: ?museum=&q=&on_view=&printable=&department=&page=
GET /api/objects/{id}               one object's details
GET /api/objects/{id}/image         its image (?size=thumb|large), only if the rights allow reuse
GET /api/objects/{id}/blurb         the AI-written page text (cached), or the museum's caption as a fallback
POST /api/scan                      a visitor's photo -> find the object -> write its page -> add it to their book
GET  /api/book, PUT /api/book       the visitor's book (ordered object IDs), keyed by the X-Visitor-Id header
GET  /api/added, POST /api/added    objects the visitor added themselves (private to them; see added.py)
PUT  /api/added/{id}, DELETE ...    change or delete one of them
GET /api/usage                      token totals from output/usage_log.jsonl
"""

from __future__ import annotations

import base64
import binascii
import json
import re

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import added
import agent
import books
import images
import scanner
from catalog import Catalog
from models import BlurbResponse, ScanResponse

app = FastAPI(title="Yale Museum Keepsake")
catalog = Catalog()
# Visitor blurbs for each museum (facts from the museums' own websites; see the file's sources)
MUSEUM_INFO = {k: v for k, v in json.loads((agent.HERE / "museum_info.json").read_text(encoding="utf-8")).items()
               if not k.startswith("_")}


@app.get("/api/health")
def health():
    return {"data": str(catalog.data_dir.relative_to(agent.ROOT)), "objects": len(catalog.by_id),
            "museums": len(catalog.museums), "model": agent.MODEL_NAME, "api_key_set": agent.key_present(),
            "tokens_today": agent.tokens_spent_today(), "daily_token_budget": agent.DAILY_TOKEN_BUDGET}


@app.get("/api/museums")
def museums():
    return [{**m, "info": MUSEUM_INFO.get(m["slug"])} for m in catalog.museum_list()]


@app.get("/api/objects")
def objects(museum: str | None = None, q: str = Query("", max_length=200), on_view: bool = False,
            printable: bool = False, department: str | None = None, page: int = Query(1, ge=1, le=1000)):
    if museum and museum not in catalog.museums:
        raise HTTPException(404, "No such museum")
    return catalog.search(museum, q, on_view, printable, department, page)


@app.get("/api/objects/{oid}")
def object_detail(oid: str, request: Request):
    d = catalog.detail(oid)
    if not d:
        rec = added.get(visitor_id(request), oid)
        if not rec:
            raise HTTPException(404, "No such object")
        return added.detail(rec, museum_name(rec["museum"]))
    d["related"] = catalog.related(oid)
    return d


@app.get("/api/objects/{oid}/image")
def object_image(oid: str, size: str = Query("thumb", pattern="^(thumb|large)$")):
    obj = catalog.by_id.get(oid)
    if not obj:
        raise HTTPException(404, "No such object")
    try:
        path = images.get_image(obj, size)
    except images.ImageNotAllowed as exc:
        raise HTTPException(403, f"Image not shown: {exc}")
    except Exception as exc:
        raise HTTPException(404, f"Image unavailable: {exc}")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/objects/{oid}/blurb", response_model=BlurbResponse)
async def object_blurb(oid: str, request: Request):
    if oid not in catalog.by_id:
        if not added.get(visitor_id(request), oid):
            raise HTTPException(404, "No such object")
        return await agent.get_added_blurb(catalog, visitor_id(request), oid)
    return await agent.get_blurb(catalog, oid, visitor=visitor_id(request))


def visitor_id(request: Request) -> str:
    return (request.headers.get("x-visitor-id") or (request.client.host if request.client else "anon"))[:64]


def museum_name(slug: str) -> str:
    return catalog.museums[slug].name if slug in catalog.museums else slug


def in_book(visitor: str, ids: list[str]) -> list[str]:
    """IDs that are real objects: in the collection, or added by this visitor."""
    mine = {r["id"] for r in added.list_added(visitor)}
    return [i for i in ids if i in catalog.by_id or i in mine]


class ScanRequest(BaseModel):
    image: str = Field(description="data URL: data:image/jpeg;base64,...", max_length=9_000_000)


class BookBody(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=books.MAX_PAGES)


@app.post("/api/scan", response_model=ScanResponse)
async def scan(body: ScanRequest, request: Request):
    m = re.match(r"^data:(image/(?:jpeg|png|webp));base64,(.+)$", body.image, re.S)
    if not m:
        raise HTTPException(415, "Send a JPEG, PNG or WebP photo.")
    try:
        data = base64.b64decode(m.group(2), validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "The photo couldn't be read.")
    if len(data) > 6_000_000:
        raise HTTPException(413, "That photo is too large (max 6 MB).")
    return await scanner.run_scan(catalog, data, m.group(1), visitor_id(request))


@app.get("/api/book")
def get_book(request: Request):
    return {"ids": in_book(visitor_id(request), books.get_book(visitor_id(request)))}


@app.put("/api/book")
def put_book(body: BookBody, request: Request):
    return {"ids": books.set_book(visitor_id(request), in_book(visitor_id(request), body.ids))}


# ---- objects a visitor adds themselves (private to them) -----------------------------------------

class AddBody(added.AddedFields):
    confirm_new: bool = Field(False, description="True once the visitor has said it isn't one of the suggested matches")


def owner(request: Request) -> str:
    """Added objects are kept only under the browser's own visitor ID, never under an IP address."""
    v = request.headers.get("x-visitor-id", "")
    if not re.fullmatch(r"[A-Za-z0-9-]{8,64}", v):
        raise HTTPException(400, "Missing visitor ID.")
    return v


def check_museum(slug: str):
    if slug not in catalog.museums:
        raise HTTPException(422, "Choose one of the museums.")


@app.get("/api/added")
def list_added(request: Request):
    return [added.card(r, museum_name(r["museum"])) for r in added.list_added(owner(request))]


@app.post("/api/added")
def create_added(body: AddBody, request: Request):
    """Add an object to the visitor's book. First checks whether it's already in Yale's collection; if it
    might be, returns the likely matches instead, and the visitor confirms (confirm_new) or saves a match."""
    who = owner(request)
    check_museum(body.museum)
    if not body.confirm_new:
        found = catalog.find(title=body.title, maker=body.maker, object_number=body.object_number)
        likely = [c for c in found if catalog.confident(c) or c["match"] in ("title", "maker and some title words")]
        if likely:
            return {"status": "possible_duplicates", "candidates": likely[:3]}
    try:
        rec = added.create(who, added.AddedFields(**body.model_dump(exclude={"confirm_new"})))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    note = ""
    try:
        ids, _ = books.add_to_book(who, rec["id"])
    except ValueError as exc:                         # the book is full: the object is kept, not added
        ids, note = books.get_book(who), str(exc)
    return {"status": "created", "object": added.card(rec, museum_name(rec["museum"])), "book": ids, "note": note}


@app.put("/api/added/{oid}")
def update_added(oid: str, body: added.AddedFields, request: Request):
    check_museum(body.museum)
    rec = added.update(owner(request), oid, body)
    if not rec:
        raise HTTPException(404, "No such object")
    return {"object": added.card(rec, museum_name(rec["museum"]))}


@app.delete("/api/added/{oid}")
def delete_added(oid: str, request: Request):
    who = owner(request)
    if not added.delete(who, oid):
        raise HTTPException(404, "No such object")
    return {"book": books.set_book(who, [i for i in books.get_book(who) if i != oid])}


@app.get("/api/usage")
def usage():
    rows = []
    if agent.USAGE_LOG.exists():
        rows = [json.loads(line) for line in agent.USAGE_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    scans = [r for r in rows if r.get("kind") == "scan"]
    rows = [r for r in rows if r.get("kind", "blurb") == "blurb"]
    ai = [r for r in rows if r["outcome"] == "ok"]
    n = len(ai) or 1
    s_ok = [r for r in scans if r["outcome"] == "ok"]
    ns = len(s_ok) or 1
    return {
        "scans": {"runs": len(scans), "ok": len(s_ok),
                  "added": sum(r["object_id"] != "scan" for r in s_ok),
                  "avg_input_tokens": round(sum(r["input_tokens"] for r in s_ok) / ns),
                  "avg_cached_input_tokens": round(sum(r["cache_read_tokens"] for r in s_ok) / ns),
                  "avg_output_tokens": round(sum(r["output_tokens"] for r in s_ok) / ns),
                  "avg_requests": round(sum(r["requests"] for r in s_ok) / ns, 2),
                  "avg_seconds": round(sum(r["seconds"] for r in s_ok) / ns, 2)},
        "runs": len(rows),
        "by_outcome": {o: sum(r["outcome"] == o for r in rows) for o in sorted({r["outcome"] for r in rows})},
        "ai_blurbs": len(ai),
        "avg_input_tokens": round(sum(r["input_tokens"] for r in ai) / n),
        "avg_cached_input_tokens": round(sum(r["cache_read_tokens"] for r in ai) / n),
        "avg_output_tokens": round(sum(r["output_tokens"] for r in ai) / n),
        "avg_requests": round(sum(r["requests"] for r in ai) / n, 2),
        "avg_seconds": round(sum(r["seconds"] for r in ai) / n, 2),
        "retries": sum(r["retries"] for r in ai),
    }
