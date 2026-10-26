"""Each visitor's book (the ordered list of saved object IDs), kept on the server so the scanner's
add_to_book tool can add to it. Only object IDs are stored, under the random visitor ID the browser
makes; the book's title and the visitor's name stay in their browser."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from catalog import ROOT

BOOKS = ROOT / "data" / "books"
MAX_PAGES = 60
_lock = threading.Lock()


def _path(visitor: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9-]", "", visitor)[:64] or "anon"
    return BOOKS / f"{safe}.json"


def get_book(visitor: str) -> list[str]:
    p = _path(visitor)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def set_book(visitor: str, ids: list[str]) -> list[str]:
    clean = list(dict.fromkeys(i for i in ids if isinstance(i, str) and re.fullmatch(r"[a-f0-9-]{36}", i)))[:MAX_PAGES]
    with _lock:
        BOOKS.mkdir(parents=True, exist_ok=True)
        _path(visitor).write_text(json.dumps(clean), encoding="utf-8")
    return clean


def add_to_book(visitor: str, oid: str) -> tuple[list[str], bool]:
    """(book, added). Adding something already in the book changes nothing."""
    with _lock:
        ids = get_book(visitor)
        if oid in ids:
            return ids, False
        if len(ids) >= MAX_PAGES:
            raise ValueError(f"The book is full ({MAX_PAGES} pages).")
        ids.append(oid)
        BOOKS.mkdir(parents=True, exist_ok=True)
        _path(visitor).write_text(json.dumps(ids), encoding="utf-8")
    return ids, True
