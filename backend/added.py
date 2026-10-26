"""Objects a visitor adds themselves, for things that aren't in our copy of Yale's collection.

Private to the visitor who adds them: kept under their random visitor ID in data/added/ (not committed),
never shown in browsing or search, and readable only with that visitor's ID. The details are what the
visitor typed, not the museum's record, and every page built from them says so. Their photo, if any,
stays in their browser like any other "your photo".
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from catalog import ROOT

ADDED = ROOT / "data" / "added"
MAX_ADDED = 60
SOURCE = "Added by you"            # shown where a museum object shows its image rights
_lock = threading.Lock()


class AddedFields(BaseModel):
    """What the visitor types. Museum, title, maker, date and type are required; the rest are optional."""

    museum: str = Field(min_length=1, max_length=40, description="A museum slug from /api/museums")
    title: str = Field(min_length=1, max_length=200)
    maker: str = Field(min_length=1, max_length=150, description="As on the label; 'Unknown' if it says so")
    date: str = Field(min_length=1, max_length=60, description="As on the label: '1745', 'ca. 1780', '18th century'")
    type: str = Field(min_length=1, max_length=60, description="What it is: painting, violin, fossil ...")
    medium: str = Field("", max_length=200)
    dimensions: str = Field("", max_length=120)
    department: str = Field("", max_length=80)
    object_number: str = Field("", max_length=40)
    label_text: str = Field("", max_length=1500, description="The wall label's text, copied by the visitor")
    note: str = Field("", max_length=500, description="The visitor's own note; printed, never sent to the AI")

    @field_validator("*", mode="before")
    @classmethod
    def tidy(cls, v):
        if isinstance(v, str):
            v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)   # control characters
            v = re.sub(r"[ \t]+", " ", v).strip()
        return v


def _path(visitor: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9-]", "", visitor)[:64] or "anon"
    return ADDED / f"{safe}.json"


def list_added(visitor: str) -> list[dict]:
    p = _path(visitor)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def get(visitor: str, oid: str) -> dict | None:
    return next((r for r in list_added(visitor) if r["id"] == oid), None)


def _write(visitor: str, records: list[dict]):
    ADDED.mkdir(parents=True, exist_ok=True)
    tmp = _path(visitor).with_suffix(".tmp")
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(_path(visitor))


def create(visitor: str, fields: AddedFields) -> dict:
    with _lock:
        records = list_added(visitor)
        if len(records) >= MAX_ADDED:
            raise ValueError(f"You've added {MAX_ADDED} objects, the most one visitor can add.")
        rec = {"id": str(uuid.uuid4()), "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               **fields.model_dump(), "blurb": None, "blurb_key": ""}
        records.append(rec)
        _write(visitor, records)
    return rec


def update(visitor: str, oid: str, fields: AddedFields) -> dict | None:
    """Change the details. The description is rewritten next time, because its key includes the facts."""
    with _lock:
        records = list_added(visitor)
        rec = next((r for r in records if r["id"] == oid), None)
        if rec is None:
            return None
        rec.update(fields.model_dump())
        _write(visitor, records)
    return rec


def delete(visitor: str, oid: str) -> bool:
    with _lock:
        records = list_added(visitor)
        keep = [r for r in records if r["id"] != oid]
        if len(keep) == len(records):
            return False
        _write(visitor, keep)
    return True


def save_blurb(visitor: str, oid: str, key: str, blurb: dict):
    """The description lives with the object (not in the shared blurb cache, which is committed)."""
    with _lock:
        records = list_added(visitor)
        for r in records:
            if r["id"] == oid:
                r["blurb"], r["blurb_key"] = blurb, key
        _write(visitor, records)


# ---- shaped like the catalogue's cards and details, so the app shows them the same way ----------

def card(rec: dict, museum_name: str) -> dict:
    return {
        "id": rec["id"],
        "title": rec["title"],
        "maker": rec["maker"],
        "collected_by": "",
        "date": rec["date"],
        "date_kind": "",
        "type": rec["type"],
        "museum": museum_name,
        "museum_slug": rec["museum"],
        "department": rec["department"],
        "accession_number": rec["object_number"],
        "on_view": False,
        "location": "",
        "image_usable": False,
        "rights": SOURCE,
        "added_by_visitor": True,
    }


def detail(rec: dict, museum_name: str) -> dict:
    return {
        **card(rec, museum_name),
        "creators_display": rec["maker"],
        "collectors": "", "classification": "", "culture": "", "period": "", "description": "",
        "medium": rec["medium"],
        "dimensions": rec["dimensions"],
        "credit_line": "", "access_statement": "", "alt_text": "", "notes": {},
        "image_rights_statement": "", "image_flag_reason": "", "object_copyright": "", "image_count": 0,
        "museum_page_url": "", "lux_url": "", "iiif_manifest_url": "",
        "label_text": rec["label_text"],
        "visitor_note": rec["note"],
        "related": [],
    }


def facts(rec: dict, museum_name: str) -> dict:
    """What the description writer may use: the visitor's details, minus their personal note."""
    f = {"title": rec["title"], "maker": rec["maker"], "date": rec["date"], "type": rec["type"],
         "medium": rec["medium"], "dimensions": rec["dimensions"], "museum": museum_name,
         "department": rec["department"], "accession_number": rec["object_number"],
         "wall_label_text": rec["label_text"]}
    return {k: v for k, v in f.items() if v}
