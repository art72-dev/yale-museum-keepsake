#!/usr/bin/env python3
"""Harvest Yale museum objects from LUX (https://lux.collections.yale.edu).

Run every command from the Final Project folder:

    python harvest/lux_harvest.py discover              # holding units, departments, counts -> data/lux/units.json
    python harvest/lux_harvest.py sample --n 20         # 20 records per museum -> data/lux/samples/
    python harvest/lux_harvest.py harvest --scope on_view   # full harvest (resumable) -> data/lux/full/
    python harvest/lux_harvest.py remap samples         # rebuild outputs from the raw cache, no refetching
    python harvest/lux_harvest.py report data/lux/samples   # coverage + rights report -> output/

Rules this script follows:
- One request per second (LUX, IIIF manifests, everything), a descriptive User-Agent,
  retries with exponential backoff on 429 / 5xx / network errors (Retry-After honoured).
- Never invents values: a field LUX doesn't have stays empty and is counted in the report.
- An image is marked usable only if its rights statement is public domain / CC0
  (see classify_rights). Everything else is flagged.
- `harvest` is resumable: stop it any time (Ctrl-C) and rerun the same command.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent          # the Final Project folder
DATA = ROOT / "data" / "lux"
RAW_SAMPLES = DATA / "raw" / "samples"                  # raw LUX + IIIF JSON for the samples (not in git)
OUTPUT = ROOT / "output"

LUX = "https://lux.collections.yale.edu"
API = LUX + "/api"
USER_AGENT = ("YaleMuseumKeepsake/0.1 (Yale SOM MGT 409 student project; "
              "polite harvester, 1 request/second)")
if os.environ.get("LUX_CONTACT"):                      # optional contact for the LUX team
    USER_AGENT += f" contact: {os.environ['LUX_CONTACT']}"

PAGE_LENGTH = 100                                      # LUX caps pageLength at 100
HMO = {"recordType": "HumanMadeObject"}                # museum objects, not digital resources

# Short names for the holding units LUX uses (keyed by the unit's LUX URI).
# New units that appear in LUX later are still harvested, under a slug made from their name.
UNIT_SLUGS = {
    f"{LUX}/data/group/41310ca5-8137-45fe-ac2c-a6a04e2235f1": "yuag",
    f"{LUX}/data/group/0a5ed086-396b-4cc2-8120-fdc3f8953ce2": "peabody",
    f"{LUX}/data/group/0e8bc04a-6538-4792-b82a-9e0751857e7d": "ycba",
    f"{LUX}/data/group/b03fe2c1-df68-4216-9e2e-85baa1d8f766": "musical_instruments",
    f"{LUX}/data/group/df7794f9-0254-4c12-bd30-04ea9836ec88": "campus_art",
    f"{LUX}/data/group/13a31506-6070-4c15-99cd-fcb5ce75ea1b": "elizabethan_club",
    f"{LUX}/data/group/6e15bc74-fc7c-425f-9ae0-0123c1adf405": "lens_media_lab",
    f"{LUX}/data/group/263b99d2-c169-4802-b72d-f59a96bf2aac": "paul_mellon_centre",
    f"{LUX}/data/group/d07b9b86-0a1e-4026-aa4c-8ecba8bbd9c9": "yale_library",
}

# Collections inside a unit that we also treat as their own "museum" (matched by name in LUX).
SUB_COLLECTIONS = {
    "babylonian_collection": "Babylonian Collection, Yale Peabody Museum",
    "lewis_walpole_library": "Lewis Walpole Library, Yale University Library",
}

# Server-side "on view" filter. LUX has no on-view field, so this is a phrase search on the
# access statement; "Not on view" also contains "on view", hence the NOT clause. Results are
# re-checked against the real access statement after each record is fetched (on_view == "yes").
ON_VIEW_FILTER = [
    {"OR": [{"text": '"on view"'}, {"text": '"on exhibit"'}]},
    {"NOT": [{"text": '"not on view"'}, {"text": '"not on exhibit"'}]},
]

# ---------------------------------------------------------------------------------------------
# HTTP: one polite client for every request
# ---------------------------------------------------------------------------------------------


class Blocked(Exception):
    """LUX refused requests (HTTP 403) even after long pauses: stop and resume later."""


class Client:
    def __init__(self, min_interval: float = 1.0, max_tries: int = 6):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.min_interval = min_interval
        self.max_tries = max_tries
        self._last = 0.0
        self.stats = Counter()

    def _wait(self):
        gap = time.monotonic() - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last = time.monotonic()

    # LUX sits behind CloudFront. A 403 there means "too many requests from this address": we pause
    # for minutes, then continue more slowly. We never change headers to get around it.
    BLOCK_PAUSES = (300, 900, 1800)                    # seconds; after the last one we stop

    def get_json(self, url: str, params: dict | None = None):
        """GET a JSON document. Returns None for 404/410. Raises Blocked if LUX keeps refusing (403)
        and RuntimeError after max_tries other failures."""
        attempt, blocks = 0, 0
        while True:
            attempt += 1
            self._wait()
            self.stats["requests"] += 1
            try:
                r = self.session.get(url, params=params, timeout=60)
            except requests.RequestException as exc:
                wait, why = self._backoff(attempt), f"{type(exc).__name__}"
            else:
                if r.status_code == 200:
                    try:
                        return r.json()
                    except ValueError:
                        wait, why = self._backoff(attempt), "invalid JSON"
                elif r.status_code in (404, 410):
                    self.stats["not_found"] += 1
                    return None
                elif r.status_code == 403:
                    self.stats["blocked"] += 1
                    if blocks == len(self.BLOCK_PAUSES):
                        raise Blocked(f"LUX keeps answering 403 for {r.url}")
                    pause = self.BLOCK_PAUSES[blocks]
                    blocks += 1
                    attempt -= 1                         # a block pause isn't a failed try
                    self.min_interval = min(5.0, self.min_interval * 1.5)
                    print(f"    LUX answered 403 (rate limit). Pausing {pause // 60} min, then continuing "
                          f"at 1 request per {self.min_interval:.1f}s", file=sys.stderr, flush=True)
                    time.sleep(pause)
                    continue
                elif r.status_code in (429, 500, 502, 503, 504):
                    retry_after = r.headers.get("Retry-After", "")
                    wait = float(retry_after) if retry_after.isdigit() else self._backoff(attempt)
                    why = f"HTTP {r.status_code}"
                else:
                    raise RuntimeError(f"HTTP {r.status_code} for {r.url}: {r.text[:300]}")
            if attempt >= self.max_tries:
                raise RuntimeError(f"Gave up after {attempt} tries ({why}): {url}")
            self.stats["retries"] += 1
            print(f"    retry {attempt}/{self.max_tries - 1} in {wait:.0f}s ({why})", file=sys.stderr, flush=True)
            time.sleep(wait)

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(120.0, 2 ** attempt) + random.uniform(0, 1)

    # LUX endpoints ---------------------------------------------------------------------------

    def estimate(self, query: dict) -> int:
        d = self.get_json(API + "/search-estimate/item", {"q": json.dumps(query)})
        return int((d or {}).get("totalItems", 0))

    def search_page(self, query: dict, page: int, page_length: int = PAGE_LENGTH) -> list[str]:
        d = self.get_json(API + "/search/item",
                          {"q": json.dumps(query), "page": page, "pageLength": page_length})
        return [it["id"] for it in (d or {}).get("orderedItems", [])]

    def facet(self, query: dict, name: str) -> list[tuple[int, str]]:
        d = self.get_json(API + "/facets/item",
                          {"q": json.dumps(query), "name": name, "pageLength": 100})
        return [(it["totalItems"], it["value"]) for it in (d or {}).get("orderedItems", [])]


# ---------------------------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------------------------


def unit_query(unit_uri: str) -> dict:
    """Objects in any collection curated by the unit or by one of its departments.
    This is the same query LUX's own 'Responsible Units' facet uses."""
    return {"memberOf": {"curatedBy": {"OR": [{"memberOf": {"id": unit_uri}}, {"id": unit_uri}]}}}


def museum_query(museum: dict, scope: str = "all") -> dict:
    base = unit_query(museum["unit_uri"]) if museum["kind"] == "unit" else {"memberOf": {"id": museum["set_uri"]}}
    parts = [base, HMO]
    if scope == "images":
        parts.append({"hasDigitalImage": 1})
    elif scope == "on_view":
        parts.extend(ON_VIEW_FILTER)
    elif scope != "all":
        raise ValueError(f"unknown scope {scope!r}")
    return {"AND": parts}


# ---------------------------------------------------------------------------------------------
# Linked Art helpers
# ---------------------------------------------------------------------------------------------


def labels(node) -> list[str]:
    return [c.get("_label", "") for c in (node or {}).get("classified_as", []) if isinstance(c, dict)]


def labels_lower(node) -> set[str]:
    return {l.lower() for l in labels(node)}


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def lang_ok(node) -> bool:
    """True if the text has no language tag or is tagged English."""
    langs = [(l.get("_label") or "").lower() for l in node.get("language", [])]
    return not langs or any(l in ("english", "eng", "en") for l in langs)


def statements(rec: dict) -> dict[str, list[str]]:
    """All referred_to_by texts grouped by their (first) classification label."""
    out: dict[str, list[str]] = defaultdict(list)
    for s in rec.get("referred_to_by", []):
        content = (s.get("content") or "").strip()
        if not content or not lang_ok(s):
            continue
        key = (labels(s) or [s.get("_label") or "Unlabelled"])[0]
        if content not in out[key]:
            out[key].append(content)
    return dict(out)


def pick(st: dict[str, list[str]], *names: str) -> str:
    wanted = {n.lower() for n in names}
    vals = [v for k, vs in st.items() if k.lower() in wanted for v in vs]
    return " | ".join(vals)


def year_of(iso: str | None) -> str:
    m = re.match(r"^(-?\d{1,6})-", iso or "")
    return str(int(m.group(1))) if m else ""


def timespan_fields(ts: dict | None) -> tuple[str, str, str]:
    if not ts:
        return "", "", ""
    display = ""
    for n in ts.get("identified_by", []):
        if n.get("content"):
            display = n["content"].strip()
            break
    y0, y1 = year_of(ts.get("begin_of_the_begin")), year_of(ts.get("end_of_the_end"))
    if y0 == y1 == "1" and display.lower() in ("n.d.", "n.d", "undated", "no date", ""):
        y0 = y1 = ""          # LUX stores 0001-01-01..0001-12-31 as a placeholder for "no date"
    return display, y0, y1


def agents_from(activity: dict | None) -> list[dict]:
    """People/groups who carried out an activity (Production or Encounter) and its parts."""
    out = []
    if not activity:
        return out
    for node in [activity] + as_list(activity.get("part")):
        role = ", ".join(labels(node))
        for a in as_list(node.get("carried_out_by")):
            out.append({"uri": a.get("id", ""), "label": (a.get("_label") or "").strip(), "role": role})
    return out


def web_links(rec: dict) -> tuple[str, str]:
    """(museum web page, IIIF v3 manifest) from subject_of."""
    page, manifest_v3, manifest_any = "", "", ""
    for so in rec.get("subject_of", []):
        label = (so.get("_label") or "").lower()
        for d in so.get("digitally_carried_by", []):
            for ap in d.get("access_point", []):
                url = ap.get("id", "")
                if not url:
                    continue
                is_manifest = "manifest" in label or "manifest" in url or any(
                    "presentation" in (c.get("id") or "") for c in d.get("conforms_to", []))
                if is_manifest:
                    if "v2" in label or "/v2/" in url:
                        manifest_any = manifest_any or url
                    elif not manifest_v3:
                        manifest_v3 = url
                elif not page and ("web page" in labels_lower(d) or (d.get("format") == "text/html")
                                   or "view this record" in label or "home" in label or "page" in label):
                    page = url
    return page, manifest_v3 or manifest_any


def thumbnail(rec: dict) -> str:
    for rep in rec.get("representation", []):
        if "wikidata" in (rep.get("_label") or "").lower():
            continue                                    # a Wikimedia copy, not the museum's image
        for d in rep.get("digitally_shown_by", []):
            for ap in d.get("access_point", []):
                if ap.get("id"):
                    return ap["id"]
    return ""


IDENTIFIER_PRIORITY = ["accession number", "ypm external catalog number", "object number", "call number"]


def accession(rec: dict) -> tuple[str, str]:
    ids = [i for i in rec.get("identified_by", []) if i.get("type") == "Identifier" and i.get("content")]
    for want in IDENTIFIER_PRIORITY:
        for i in ids:
            if want in labels_lower(i):
                return i["content"].strip(), labels(i)[0]
    skip = {"system-assigned number", "sort value", "ypm emu irn", "ypm internal catalog number"}
    for i in ids:
        if not (labels_lower(i) & skip):
            return i["content"].strip(), (labels(i) or [""])[0]
    return "", ""


def other_identifiers(rec: dict, used: str) -> str:
    out = []
    for i in rec.get("identified_by", []):
        if i.get("type") == "Identifier" and i.get("content") and i["content"].strip() != used:
            if not (labels_lower(i) & {"sort value"}):
                out.append(f"{(labels(i) or ['Identifier'])[0]}: {i['content'].strip()}")
    return " | ".join(out)


def title_of(rec: dict) -> tuple[str, list[str]]:
    """(title, other names). YUAG tags titles 'Primary Title', YCBA 'Primary'; YCBA also tags the
    series a print belongs to 'Collective title' + 'Primary Name', so that one is skipped."""
    names = [n for n in rec.get("identified_by", []) if n.get("type") == "Name" and n.get("content")]
    title = ""
    for want in ("primary title", "primary", "primary name"):
        for n in names:
            tags = labels_lower(n)
            if want in tags and "collective title" not in tags and lang_ok(n):
                title = n["content"].strip()
                break
        if title:
            break
    title = title or (rec.get("_label") or "").strip()
    others = [n["content"].strip() for n in names if n["content"].strip() != title]
    return title, others


# Classification labels that say nothing about what the object is.
GENERIC_TYPES = {"collection item", "visual works", "physical object"}


def classification(rec: dict) -> tuple[str, str]:
    object_type, other = [], []
    for c in rec.get("classified_as", []):
        lab = (c.get("_label") or "").strip()
        if not lab or lab.lower() in GENERIC_TYPES:
            continue
        meta = labels_lower(c)
        (object_type if meta & {"type of work", "type of object"} else other).append(lab)
    return " | ".join(object_type), " | ".join(other)


def structured_dimensions(rec: dict) -> str:
    out = []
    for d in rec.get("dimension", []):
        kind = ", ".join(labels(d)) or "dimension"
        unit = (d.get("unit") or {}).get("_label", "")
        if d.get("value") is not None:
            out.append(f"{kind}: {d['value']} {unit}".strip())
    return "; ".join(out)


def on_view_flag(access: str) -> str:
    """'yes' if any access statement starts 'On view' / 'on exhibit', 'no' if there are statements
    but none says so, '' if the record has no access statement."""
    parts = [p.strip().lower() for p in access.split(" | ") if p.strip()]
    if any(p.startswith(("on view", "on exhibit")) for p in parts):
        return "yes"
    return "no" if parts else ""


# ---------------------------------------------------------------------------------------------
# IIIF manifests and image rights
# ---------------------------------------------------------------------------------------------


def iiif_text(x) -> str:
    if isinstance(x, dict):
        vals = x.get("en") or x.get("none") or next(iter(x.values()), [])
        return " ".join(v for v in vals if isinstance(v, str)).strip()
    if isinstance(x, list):
        return " ".join(iiif_text(i) for i in x).strip()
    return str(x or "").strip()


def metadata_value(meta: list, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for m in meta or []:
        if iiif_text(m.get("label")).lower() in wanted:
            return iiif_text(m.get("value"))
    return ""


DATE_LABELS = ("Date", "Published/Created Date", "Date Created", "Created", "Creation Date")


def years_in(text: str) -> list[int]:
    """Years written in a date text: 4-digit years, plus short ranges such as "1900-55" (= 1955)."""
    years = [int(y) for y in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", text)]
    for full, short in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})\s*[-–]\s*(\d{2})(?!\d)", text):
        years.append(int(full[:2] + short))
    return years


def manifest_date(m: dict | None) -> tuple[str, str, str]:
    """(display, earliest year, latest year) from the IIIF manifest's own date field, e.g. the Library's
    "publish'd as the act directs, June 1773." Years are only the years written there."""
    text = metadata_value((m or {}).get("metadata"), *DATE_LABELS)
    years = years_in(text)
    return (text, str(min(years)), str(max(years))) if years else (text, "", "")


def parse_manifest(m: dict | None) -> dict:
    """Image URL, size, alt text and the rights statement that applies to the image itself."""
    out = {"image_url": "", "image_service": "", "image_count": "", "image_width": "", "image_height": "",
           "alt_text": "", "image_rights_statement": "", "image_rights_uri": "", "image_rights_level": "",
           "object_copyright": "", "manifest_metadata_rights": ""}
    if not m:
        return out
    canvases = m.get("items") or []
    out["image_count"] = len(canvases)
    meta = m.get("metadata", [])
    out["alt_text"] = metadata_value(meta, "Alternative Text")
    out["object_copyright"] = metadata_value(meta, "Copyright Statement")
    canvas_rights = ""
    if canvases:
        c = canvases[0]
        try:
            body = c["items"][0]["items"][0]["body"]
            out["image_url"] = body.get("id", "")
            svc = as_list(body.get("service"))
            out["image_service"] = (svc[0].get("@id") or svc[0].get("id") or "") if svc else ""
            out["image_width"], out["image_height"] = body.get("width", c.get("width", "")), body.get("height", c.get("height", ""))
        except (KeyError, IndexError, TypeError):
            pass
        canvas_rights = metadata_value(c.get("metadata"), "Image Use Rights", "Rights")
    manifest_rights_text = metadata_value(meta, "Rights", "Image Use Rights")
    required = iiif_text((m.get("requiredStatement") or {}).get("value"))
    out["manifest_metadata_rights"] = required

    if canvas_rights:                                   # most specific: rights of this image
        out.update(image_rights_statement=canvas_rights, image_rights_level="image")
    elif manifest_rights_text:
        out.update(image_rights_statement=manifest_rights_text, image_rights_level="manifest")
    elif m.get("rights"):
        # YUAG/YCBA/LML put a CC0 (or CC BY) licence on the manifest but say in requiredStatement that it
        # covers the *data* and that "restrictions may apply" to images. Then it is not an image licence.
        if re.search(r"restrictions may apply", required, re.I):
            out.update(image_rights_statement=required, image_rights_uri=m["rights"], image_rights_level="metadata-only")
        else:
            out.update(image_rights_statement=required, image_rights_uri=m["rights"], image_rights_level="manifest")
    return out


USABLE = {"CC0", "Public domain", "No Copyright - United States"}

# Yale's Open Access policy (2011, https://guides.library.yale.edu/openaccess): digital images of works in Yale's
# museum, library and archive collections that are believed to be in the public domain "may be used by anyone for
# any purpose". Yale University Library marks its images only with a generic "may be subject to copyright" line
# (or nothing), even for 18th-century prints, so for Library objects made before 1900 we treat the image as public
# domain under that policy. Explicit copyright claims ("Copyright is retained by ...") are never overridden.
# Approved by the user on 2026-10-25.
OPEN_ACCESS_CATEGORY = "Public domain by date (Yale Open Access policy)"
OPEN_ACCESS_UNITS = {"Yale University Library"}
OPEN_ACCESS_BEFORE = 1900
OPEN_ACCESS_OVERRIDES = {"Unclear (may be in copyright)", "No rights statement"}


def open_access_by_date(row: dict) -> dict:
    """Mark a Library image usable when the work was made before 1900 (see OPEN_ACCESS_CATEGORY)."""
    latest = row.get("date_latest_year", "")
    if (row.get("holding_museum") in OPEN_ACCESS_UNITS and row.get("iiif_manifest_url")
            and row.get("image_rights_category") in OPEN_ACCESS_OVERRIDES
            and re.fullmatch(r"-?\d+", latest or "") and int(latest) < OPEN_ACCESS_BEFORE):
        row.update(image_rights_category=OPEN_ACCESS_CATEGORY, image_usable="yes", image_flag_reason="",
                   image_rights_note=f"Made by {latest}, before {OPEN_ACCESS_BEFORE}: public domain, usable under "
                                     f"Yale's Open Access policy. The Library's own statement: "
                                     f"{row.get('image_rights_statement') or 'none'}")
    return row


def classify_rights(statement: str, uri: str, level: str, object_copyright: str) -> tuple[str, str, str]:
    """(category, usable 'yes'/'no', reason). Usable only for public domain / CC0 images."""
    s, u = re.sub(r"[–—]", "-", statement.lower()), uri.lower()
    if not statement and not uri:
        cat = "No rights statement"
    elif level == "metadata-only":
        cat = "Licence covers metadata only"
    elif "publicdomain/zero" in u or "cc0" in s:
        cat = "CC0"
    elif "no copyright - united states" in s or "noc-us" in u:
        cat = "No Copyright - United States"
    elif "publicdomain/mark" in u or s.startswith("public domain"):
        cat = "Public domain"
    elif "creativecommons.org/licenses/" in u or re.search(r"\bcc by\b", s):
        cat = "Creative Commons (attribution/other)"
    elif "not assigned" in s:
        cat = "Not assigned"
    elif "undetermined" in s:
        cat = "Copyright undetermined"
    elif "may be subject to" in s:
        cat = "Unclear (may be in copyright)"
    elif "copyright" in s or "rights reserved" in s or "permission" in s:
        cat = "In copyright / restricted"
    else:
        cat = "Other"
    if cat not in USABLE:
        return cat, "no", f"image rights: {cat}"
    oc = object_copyright.lower()
    if oc and "public domain" not in oc and ("copyright" in oc or "estate" in oc):
        return cat, "no", f"conflict: image says {cat} but object says '{object_copyright}'"
    return cat, "yes", ""


# ---------------------------------------------------------------------------------------------
# Record -> our fields
# ---------------------------------------------------------------------------------------------

CSV_FIELDS = [
    "lux_uri", "lux_url", "harvest_group", "holding_museum", "department", "accession_number",
    "accession_number_type", "other_identifiers", "title", "creators", "creator_names", "creator_roles", "creator_uris",
    "creator_source", "collectors", "collector_uris", "date_display", "date_earliest_year", "date_latest_year", "date_kind",
    "object_type", "classification", "medium", "materials", "dimensions", "dimensions_structured",
    "culture", "period", "description", "credit_line", "access_statement", "on_view",
    "museum_page_url", "iiif_manifest_url", "thumbnail_url", "image_url", "image_service",
    "image_count", "image_width", "image_height", "alt_text", "image_rights_statement",
    "image_rights_uri", "image_rights_level", "image_rights_category", "image_rights_note", "object_copyright",
    "image_usable", "image_flag_reason", "harvested_at",
]

# Statement labels already mapped to their own column (others are kept in the JSON "statements").
MAPPED_STATEMENTS = {"medium", "material statement", "materials", "dimensions", "dimension statement",
                     "physical statement", "culture", "period", "description", "credit line", "creditline",
                     "access statement", "visitors' statement", "citations"}


def linked_work_uri(rec: dict) -> str:
    """The work an object shows or carries (a print's image, a book's text)."""
    for w in as_list(rec.get("shows")) + as_list(rec.get("carries")):
        if (w.get("id") or "").startswith(LUX + "/data/"):
            return w["id"]
    return ""


def needs_work(rec: dict) -> bool:
    """Library records (prints, books, manuscripts) keep creators and dates on the linked work,
    not on the object. Fetch the work only when the object itself names no creator."""
    return not agents_from(rec.get("produced_by")) and bool(linked_work_uri(rec))


def map_record(rec: dict, manifest: dict | None, museum: dict, names: dict[str, str] | None = None,
               work: dict | None = None) -> dict:
    """names: agent URI -> primary name (from AgentNames). The object record only carries a display
    label for each agent, e.g. 'Artist: Vincent van Gogh (Dutch, 1853–1890)' or, for Peabody
    collectors, just 'Collector'. work: the linked work record, if needs_work() fetched it."""
    names = names or {}
    st = statements(rec)
    produced = rec.get("produced_by") or {}
    encounters = as_list(rec.get("encountered_by"))
    creators = agents_from(produced)
    creator_source = "object" if creators else ""
    created = (work or {}).get("created_by") or {}
    if not creators and work:
        creators = agents_from(created)
        creator_source = "linked work" if creators else ""
    collectors = [a for e in encounters for a in agents_from(e)]
    work_st = statements(work) if work else {}

    date_display, y0, y1 = timespan_fields(produced.get("timespan"))
    if not (date_display or y0):                        # some productions date only their parts
        for p in as_list(produced.get("part")):
            date_display, y0, y1 = timespan_fields(p.get("timespan"))
            if date_display or y0:
                break
    date_kind = "produced" if (date_display or y0) else ""
    if not date_kind and created:                       # library items: date of the linked work
        for node in [created] + as_list(created.get("part")):
            date_display, y0, y1 = timespan_fields(node.get("timespan"))
            if date_display or y0:
                date_kind = "created (linked work)"
                break
    if not date_kind and manifest:                      # library items: the image record's own date text
        date_display, y0, y1 = manifest_date(manifest)
        date_kind = "from the image record" if (date_display or y0) else ""
    if not date_kind:                                   # natural history: date collected
        for e in encounters:
            date_display, y0, y1 = timespan_fields(e.get("timespan"))
            if date_display or y0:
                date_kind = "collected"
                break

    acc, acc_type = accession(rec)
    title, other_names = title_of(rec)
    obj_type, other_types = classification(rec)
    page, manifest_url = web_links(rec)
    access = pick(st, "Access statement")
    img = parse_manifest(manifest)
    category, usable, reason = classify_rights(img["image_rights_statement"], img["image_rights_uri"],
                                               img["image_rights_level"], img["object_copyright"])
    if not manifest_url:
        category, usable, reason = "No image", "no", "no IIIF manifest"
    elif manifest is None:
        category, usable, reason = "Manifest unavailable", "no", "manifest could not be fetched"

    row = {
        "lux_uri": rec.get("id", ""),
        "lux_url": rec.get("id", "").replace("/data/", "/view/", 1),
        "harvest_group": museum["slug"],
        "holding_museum": museum["unit_label"],
        "department": " | ".join(m.get("_label", "") for m in rec.get("member_of", []) if m.get("_label")),
        "accession_number": acc,
        "accession_number_type": acc_type,
        "other_identifiers": other_identifiers(rec, acc),
        "title": title,
        "creators": " | ".join(a["label"] for a in creators),
        "creator_names": " | ".join(names.get(a["uri"], "") for a in creators) if any(
            names.get(a["uri"]) for a in creators) else "",
        "creator_roles": " | ".join(a["role"] for a in creators) if any(a["role"] for a in creators) else "",
        "creator_uris": " | ".join(a["uri"] for a in creators) if any(a["uri"] for a in creators) else "",
        "creator_source": creator_source,
        "collectors": " | ".join(n for n in (names.get(a["uri"], "") for a in collectors) if n),
        "collector_uris": " | ".join(a["uri"] for a in collectors if a["uri"]),
        "date_display": date_display,
        "date_earliest_year": y0,
        "date_latest_year": y1,
        "date_kind": date_kind,
        "object_type": obj_type,
        "classification": other_types,
        "medium": pick(st, "Medium", "Material Statement", "Materials"),
        "materials": " | ".join(m.get("_label", "") for m in rec.get("made_of", []) if m.get("_label")),
        "dimensions": pick(st, "Dimensions", "Dimension Statement", "Physical Statement")
                      or pick(work_st, "Dimensions", "Dimension Statement", "Physical Statement"),
        "dimensions_structured": structured_dimensions(rec),
        "culture": pick(st, "Culture"),
        "period": pick(st, "Period"),
        "description": pick(st, "Description"),
        "credit_line": pick(st, "Credit Line", "Creditline"),
        "access_statement": access,
        "on_view": on_view_flag(access),
        "museum_page_url": page,
        "iiif_manifest_url": manifest_url,
        "thumbnail_url": thumbnail(rec),
        **{k: img[k] for k in ("image_url", "image_service", "image_count", "image_width", "image_height",
                               "alt_text", "image_rights_statement", "image_rights_uri",
                               "image_rights_level", "object_copyright")},
        "image_rights_category": category,
        "image_rights_note": "",
        "image_usable": usable,
        "image_flag_reason": reason,
        "harvested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # JSON keeps structured creators and every other statement (provenance, inscriptions, notes...)
    row["_creators"] = creators
    row["_collectors"] = collectors
    row["_other_names"] = other_names
    row["_statements"] = {k: v for k, v in st.items() if k.lower() not in MAPPED_STATEMENTS}
    for k, v in work_st.items():                        # e.g. a print's notes and attribution line
        if k.lower() not in MAPPED_STATEMENTS:
            row["_statements"][f"Linked work: {k}"] = v
    row["_linked_work"] = (work or {}).get("id", "")
    row["_manifest_notes"] = {k: v for k in ("Abstract", "Description", "Alternative Text")
                              if (v := metadata_value((manifest or {}).get("metadata"), k))}
    if not row["creators"] and manifest:                # library item with no creator in LUX: the image record's
        who = item_creators(manifest.get("metadata"))
        if who:
            row.update(creators=" | ".join(who), creator_source="image record")
    return open_access_by_date(format_library_creators(row))


class AgentNames:
    """Primary names of people/groups, looked up once per URI and kept in data/lux/agents.json
    so reruns and resumed harvests don't fetch them again."""

    def __init__(self, client: Client, path: Path = DATA / "agents.json"):
        self.client, self.path = client, path
        self.cache: dict[str, str] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def get(self, uri: str) -> str:
        if not uri.startswith(LUX + "/data/"):
            return ""
        if uri not in self.cache:
            try:
                rec = self.client.get_json(uri) or {}
            except RuntimeError as exc:                 # name stays empty; looked up again next run
                print(f"    could not look up {uri}: {exc}", file=sys.stderr)
                return ""
            primary = [n["content"].strip() for n in rec.get("identified_by", [])
                       if n.get("type") == "Name" and n.get("content")
                       and "primary name" in labels_lower(n) and lang_ok(n)]
            self.cache[uri] = primary[0] if primary else (rec.get("_label") or "").strip()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0), encoding="utf-8")
        return self.cache[uri]


def map_with_names(rec: dict, manifest: dict | None, museum: dict, agents: AgentNames,
                   work: dict | None = None) -> dict:
    people = (agents_from(rec.get("produced_by")) + agents_from((work or {}).get("created_by"))
              + [a for e in as_list(rec.get("encountered_by")) for a in agents_from(e)])
    names = {a["uri"]: agents.get(a["uri"]) for a in people if a["uri"]}
    return map_record(rec, manifest, museum, names, work)


def fetch_and_map(client: Client, uri: str, museum: dict, agents: AgentNames,
                  raw_path: Path | None = None, extra: dict | None = None) -> dict | None:
    """Fetch the LUX record and its IIIF manifest, keep both in the raw cache, and map them."""
    rec = client.get_json(uri)
    if rec is None:
        return None
    _, manifest_url = web_links(rec)
    manifest = client.get_json(manifest_url) if manifest_url else None
    work = client.get_json(linked_work_uri(rec)) if needs_work(rec) else None
    if raw_path:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(raw_path, "at", encoding="utf-8") as f:
            f.write(json.dumps({"uri": uri, "record": rec, "manifest": manifest, "work": work, **(extra or {})},
                               ensure_ascii=False) + "\n")
    return map_with_names(rec, manifest, museum, agents, work)


def read_raw(path: Path) -> list[dict]:
    """Raw cache entries, last copy of each URI wins (an interrupted run may have written one twice)."""
    out: dict[str, dict] = {}
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    out[e["uri"]] = e
    return list(out.values())


# ---------------------------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------------------------


def write_outputs(rows: list[dict], folder: Path, slug: str):
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{slug}.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    with open(folder / f"{slug}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_combined(folder: Path, slugs: list[str]):
    seen, rows = set(), []
    for slug in slugs:
        p = folder / f"{slug}.json"
        if not p.exists():
            continue
        for r in json.loads(p.read_text(encoding="utf-8")):
            if r["lux_uri"] not in seen:
                seen.add(r["lux_uri"])
                rows.append(r)
    write_outputs(rows, folder, "all_museums")
    return len(rows)


# ---------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def cmd_discover(client: Client, args):
    """Find every holding unit LUX uses, its departments, and counts per museum."""
    every = {"OR": [HMO, {"recordType": "DigitalObject"}]}
    print("Finding holding units (LUX 'responsibleUnits' facet)...")
    unit_counts = client.facet(HMO, "responsibleUnits")
    all_types = dict((v, n) for n, v in client.facet(every, "responsibleUnits"))
    set_labels: dict[str, str] = {}
    units = []
    for n, uri in unit_counts:
        g = client.get_json(uri) or {}
        label = g.get("_label") or uri
        names = [x["content"] for x in g.get("identified_by", []) if x.get("type") == "Name"]
        print(f"  {n:>12,}  {label}")
        depts = []
        for dn, sid in client.facet({"AND": [unit_query(uri), HMO]}, "responsibleCollections"):
            if sid not in set_labels:
                set_labels[sid] = (client.get_json(sid) or {}).get("_label", sid)
            depts.append({"set_uri": sid, "label": set_labels[sid], "objects": dn})
        units.append({"unit_uri": uri, "label": label, "display_name": names[0] if names else label,
                      "slug": UNIT_SLUGS.get(uri) or slugify(label), "objects": n,
                      "all_record_types": all_types.get(uri, n), "departments": depts})

    museums = [{"slug": u["slug"], "kind": "unit", "unit_uri": u["unit_uri"], "unit_label": u["display_name"],
                "label": u["display_name"]} for u in units]
    for slug, name in SUB_COLLECTIONS.items():
        for u in units:
            hit = next((d for d in u["departments"] if d["label"].lower() == name.lower()), None)
            if hit:
                museums.append({"slug": slug, "kind": "sub_collection", "set_uri": hit["set_uri"],
                                "unit_uri": u["unit_uri"], "unit_label": u["display_name"], "label": hit["label"]})
                break
        else:
            print(f"  ! sub-collection not found in LUX: {name}")

    print("\nCounting objects per museum (all / with a digital image / on view)...")
    for m in museums:
        m["count_all"] = client.estimate(museum_query(m, "all"))
        m["count_images"] = client.estimate(museum_query(m, "images"))
        m["count_on_view_estimate"] = client.estimate(museum_query(m, "on_view"))
        print(f"  {m['label'][:58]:<58} {m['count_all']:>11,} {m['count_images']:>10,} {m['count_on_view_estimate']:>8,}")

    DATA.mkdir(parents=True, exist_ok=True)
    out = {"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "total_objects_in_lux": client.estimate(HMO), "units": units, "museums": museums}
    (DATA / "units.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {DATA / 'units.json'}  ({client.stats['requests']} requests)")


def load_museums(only: list[str] | None = None) -> list[dict]:
    p = DATA / "units.json"
    if not p.exists():
        sys.exit("Run `python harvest/lux_harvest.py discover` first.")
    museums = json.loads(p.read_text(encoding="utf-8"))["museums"]
    if only:
        unknown = set(only) - {m["slug"] for m in museums}
        if unknown:
            sys.exit(f"Unknown museum slug(s): {', '.join(sorted(unknown))}")
        museums = [m for m in museums if m["slug"] in only]
    return museums


def cmd_sample(client: Client, args):
    """N records per museum, spread across the result list (deterministic, so reruns match)."""
    folder = Path(args.out)
    museums = load_museums(args.museum)
    agents = AgentNames(client)
    for m in museums:
        cached = read_raw(RAW_SAMPLES / f"{m['slug']}.jsonl.gz")
        if args.resume and len(cached) >= args.n:      # finished in an earlier run: rebuild from cache
            rows = []
            for e in cached[: args.n]:
                row = map_with_names(e["record"], e["manifest"], m, agents, e.get("work"))
                row["sample_scope"] = e.get("sample_scope", "")
                rows.append(row)
            write_outputs(rows, folder, m["slug"])
            print(f"\n{m['label']}  [{m['slug']}]  already sampled: rebuilt {len(rows)} records from the raw cache")
            continue
        scope = args.scope
        total = client.estimate(museum_query(m, scope))
        if total == 0 and scope != "all":
            print(f"  {m['label']}: no objects for scope '{scope}', sampling from all objects instead")
            scope, total = "all", client.estimate(museum_query(m, "all"))
        q = museum_query(m, scope)
        chunks, per = 4, max(1, math.ceil(args.n / 4))
        uris: list[str] = []
        if total <= args.n:
            uris = client.search_page(q, 1, max(args.n, 1))
        else:
            for i in range(chunks):
                page = int(i * total / chunks / per) + 1
                for u in client.search_page(q, page, per):
                    if u not in uris:
                        uris.append(u)
        uris = uris[: args.n]
        print(f"\n{m['label']}  [{m['slug']}]  scope={scope}  matching={total:,}  sampling {len(uris)}")
        raw_path = RAW_SAMPLES / f"{m['slug']}.jsonl.gz"
        raw_path.unlink(missing_ok=True)
        rows = []
        for i, u in enumerate(uris, 1):
            try:
                row = fetch_and_map(client, u, m, agents, raw_path, {"sample_scope": scope})
            except RuntimeError as exc:
                print(f"  {i:>2}. FAILED {u}: {exc}", file=sys.stderr)
                continue
            if row:
                row["sample_scope"] = scope
                rows.append(row)
                print(f"  {i:>2}. {row['title'][:60]:<60} {row['image_rights_category']}")
        write_outputs(rows, folder, m["slug"])
    n = write_combined(folder, [m["slug"] for m in load_museums()])
    print(f"\nSaved per-museum files and all_museums ({n} records) in {folder}  "
          f"({client.stats['requests']} requests, {client.stats['retries']} retries)")


def cmd_harvest(client: Client, args):
    """Full, resumable harvest. Phase 1 lists record URIs page by page; phase 2 fetches each one.
    Progress lives in data/lux/full/<slug>/ so an interrupted run picks up where it stopped."""
    base = Path(args.out)
    museums = load_museums(args.museum)
    agents = AgentNames(client)
    for m in museums:
        folder = base / m["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        state_p, ids_p, rec_p = folder / "state.json", folder / "ids.txt", folder / "records.jsonl"
        q = museum_query(m, args.scope)
        state = json.loads(state_p.read_text()) if state_p.exists() else {}
        if state.get("query") != q:                      # new scope -> start this museum fresh
            for p in (ids_p, rec_p):
                p.unlink(missing_ok=True)
            state = {"query": q, "scope": args.scope, "next_page": 1, "listing_done": False,
                     "started": datetime.now(timezone.utc).isoformat()}
        state["estimate"] = client.estimate(q)
        print(f"\n{m['label']} [{m['slug']}] scope={args.scope}: about {state['estimate']:,} objects")

        ids = ids_p.read_text().split() if ids_p.exists() else []
        seen_ids = set(ids)
        limit = args.limit or math.inf
        while not state["listing_done"] and len(seen_ids) < limit:
            page_ids = client.search_page(q, state["next_page"])
            new = [u for u in page_ids if u not in seen_ids]
            with open(ids_p, "a") as f:
                f.writelines(u + "\n" for u in new)
            seen_ids.update(new)
            ids.extend(new)
            state["next_page"] += 1
            state["listing_done"] = len(page_ids) < PAGE_LENGTH
            state_p.write_text(json.dumps(state, indent=1))
            print(f"  listed page {state['next_page'] - 1}: {len(seen_ids):,} ids", end="\r")
        print()

        done = set()
        if rec_p.exists():
            with open(rec_p, encoding="utf-8") as f:
                done = {json.loads(line)["lux_uri"] for line in f if line.strip()}
        todo = [u for u in ids if u not in done][: max(0, int(min(limit, len(ids))) - len(done))]
        print(f"  {len(done):,} already fetched, {len(todo):,} to go "
              f"(~{len(todo) * 2 / 3600:.1f} h at 1 request/s, record + manifest)")
        dropped = state.get("dropped_not_on_view", 0)
        with open(rec_p, "a", encoding="utf-8") as f:
            for i, u in enumerate(todo, 1):
                try:
                    row = fetch_and_map(client, u, m, agents, folder / "raw.jsonl.gz")
                except RuntimeError as exc:              # left out of records.jsonl, so the next run retries it
                    state["failed"] = state.get("failed", 0) + 1
                    print(f"  FAILED {u}: {exc}", file=sys.stderr)
                    continue
                if row is None:
                    state["missing"] = state.get("missing", 0) + 1
                    continue
                if args.scope == "on_view" and row["on_view"] != "yes":
                    dropped += 1                         # phrase matched, but the object isn't on view
                    row["_dropped"] = "not on view"
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                if i % 25 == 0:
                    state["dropped_not_on_view"] = dropped
                    state_p.write_text(json.dumps(state, indent=1))
                    print(f"  fetched {len(done) + i:,}/{len(ids):,}", end="\r")
        state["dropped_not_on_view"] = dropped
        state["updated"] = datetime.now(timezone.utc).isoformat()
        state_p.write_text(json.dumps(state, indent=1))

        with open(rec_p, encoding="utf-8") as f:
            rows = [r for r in (json.loads(line) for line in f if line.strip()) if not r.get("_dropped")]
        write_outputs(rows, base, m["slug"])
        print(f"  wrote {len(rows):,} records to {base / (m['slug'] + '.csv')} (+ .json)")
    n = write_combined(base, [m["slug"] for m in load_museums()])
    print(f"\nall_museums: {n:,} records  ({client.stats['requests']:,} requests, {client.stats['retries']} retries)")


def cmd_remap(client: Client, args):
    """Rebuild the CSV/JSON outputs from the raw cache, without refetching records or manifests
    (only agent names not yet in data/lux/agents.json are looked up). Use after changing map_record."""
    agents = AgentNames(client)
    museums = load_museums(args.museum)
    if args.which == "samples":
        folder = DATA / "samples"
        for m in museums:
            entries = read_raw(RAW_SAMPLES / f"{m['slug']}.jsonl.gz")
            if not entries:
                continue
            rows = []
            for e in entries:
                row = map_with_names(e["record"], e["manifest"], m, agents, e.get("work"))
                row["sample_scope"] = e.get("sample_scope", "")
                rows.append(row)
            write_outputs(rows, folder, m["slug"])
            print(f"  {m['slug']}: {len(rows)} records")
    else:
        folder = DATA / "full"
        for m in museums:
            entries = read_raw(folder / m["slug"] / "raw.jsonl.gz")
            if not entries:
                continue
            state_p = folder / m["slug"] / "state.json"
            scope = json.loads(state_p.read_text()).get("scope") if state_p.exists() else ""
            rows = []
            with open(folder / m["slug"] / "records.jsonl", "w", encoding="utf-8") as f:
                for e in entries:
                    row = map_with_names(e["record"], e["manifest"], m, agents, e.get("work"))
                    if scope == "on_view" and row["on_view"] != "yes":
                        row["_dropped"] = "not on view"
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    if not row.get("_dropped"):
                        rows.append(row)
            write_outputs(rows, folder, m["slug"])
            print(f"  {m['slug']}: {len(rows)} records")
    n = write_combined(folder, [m["slug"] for m in load_museums()])
    print(f"all_museums: {n} records ({client.stats['requests']} requests)")


# ---------------------------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------------------------

REPORT_FIELDS = ["lux_uri", "accession_number", "title", "creators", "creator_names", "creator_uris", "collectors",
                 "date_display", "date_earliest_year", "date_latest_year", "object_type", "classification",
                 "medium", "materials", "dimensions", "description", "credit_line", "holding_museum",
                 "department", "access_statement", "museum_page_url", "iiif_manifest_url", "thumbnail_url",
                 "image_url", "alt_text", "image_rights_statement", "lux_url"]


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "–"


def normalize(row: dict) -> dict:
    """Re-derive the fields that are pure functions of stored values, so files written by an older
    version of map_record report the same way (rights category, the year-1 'no date' placeholder)."""
    if row.get("iiif_manifest_url") and row.get("image_rights_category") not in ("Manifest unavailable",):
        cat, usable, reason = classify_rights(row.get("image_rights_statement", ""), row.get("image_rights_uri", ""),
                                              row.get("image_rights_level", ""), row.get("object_copyright", ""))
        row.update(image_rights_category=cat, image_usable=usable, image_flag_reason=reason)
    if row.get("date_earliest_year") == row.get("date_latest_year") == "1" and \
            row.get("date_display", "").lower() in ("n.d.", "n.d", "undated", "no date", ""):
        row["date_earliest_year"] = row["date_latest_year"] = ""
    if row.get("date_kind") == "from the image record" and (years := years_in(row.get("date_display", ""))):
        row["date_earliest_year"], row["date_latest_year"] = str(min(years)), str(max(years))
    return open_access_by_date(format_library_creators(row))


ROLE_WORDS = {"printmaker", "artist", "publisher", "engraver", "etcher", "author", "printer", "bookseller", "draftsman",
              "illustrator", "photographer", "lithographer", "editor", "designer", "cartographer", "creator", "maker",
              "contributor", "binder", "calligrapher", "scribe", "compiler", "translator", "composer"}


def library_person(entry: str) -> tuple[str, str, list[str]]:
    """'Bobbin, Tim, 1708-1786, artist.' -> ('Tim Bobbin', '1708-1786', ['artist']). Library catalogue headings
    put the surname first and may add dates ('active 1791-1792', 'approximately 1760-1809') and roles."""
    s, roles = entry.strip().rstrip(".").strip(), []

    def paren(m):                                     # "(Engraver)" is a role; "(Charles Jameson)" is a name
        if m.group(1).strip().lower() in ROLE_WORDS:
            roles.append(m.group(1).strip().lower())
            return ""
        return m.group(0)
    s = re.sub(r"\s*\(([^)]*)\)", paren, s)
    while (m := re.search(r"[,\s]+([a-z]+)\.?\s*$", s)) and m.group(1) in ROLE_WORDS:
        roles.insert(0, m.group(1))
        s = s[:m.start()].rstrip(" ,")
    dates = ""
    if d := re.search(r",?\s*((?:active |approximately |ca\. |born |died )?\d{3,4}.*)$", s):
        dates, s = d.group(1).strip(), s[:d.start()].rstrip(" ,")
    parts = [p.strip() for p in re.split(r",\s*(?![^()]*\))", s) if p.strip()]
    if len(parts) == 2 and not re.search(r"\b(and|&)\b", parts[0]):
        first = re.sub(r"^.*?\((.+)\)$", r"\1", parts[1])   # "C. J. (Charles Jameson)" -> "Charles Jameson"
        name = f"{first} {parts[0]}"
    elif len(parts) == 3 and parts[2] in ("Sir", "Lady", "Dame", "Lord"):
        name = f"{parts[2]} {parts[1]} {parts[0]}"
    else:
        name = s
    return name, dates, roles


def format_library_creators(row: dict) -> dict:
    """Library makers as people read them: 'Tim Bobbin (artist, 1708–1786)' rather than the catalogue heading
    'Bobbin, Tim, 1708-1786, artist.' The heading is kept in _creators_raw, so this can be re-run safely."""
    raw = row.get("_creators_raw") or row.get("creators", "")
    if row.get("holding_museum") not in OPEN_ACCESS_UNITS or not raw:
        return row
    row["_creators_raw"] = raw
    lux_roles = row.get("_creator_roles_raw", row.get("creator_roles", "")).split(" | ")
    row["_creator_roles_raw"] = " | ".join(lux_roles)
    people: dict[str, list] = {}
    for i, entry in enumerate(raw.split(" | ")):
        name, dates, roles = library_person(entry)
        if not roles and i < len(lux_roles) and lux_roles[i].strip():
            roles = [x.strip().lower() for x in lux_roles[i].split(",") if x.strip()]
        p = people.setdefault(name, [dates, []])
        p[0] = p[0] or dates
        p[1] += [x for x in roles if x not in p[1]]
    row["creators"] = " | ".join(
        f"{n} ({', '.join(filter(None, [', '.join(rs), d.replace('-', '–')]))})" if (rs or d) else n
        for n, (d, rs) in people.items())
    row["creator_names"] = " | ".join(people)
    row["creator_roles"] = " | ".join(", ".join(rs) for _, rs in people.values())
    return row


def metadata_values(meta: list, *names: str) -> list[str]:
    """Every value of the named IIIF metadata fields, kept separate (one per person, say)."""
    wanted, out = {n.lower() for n in names}, []
    for m in meta or []:
        if iiif_text(m.get("label")).lower() in wanted:
            v = m.get("value")
            vals = [x for vs in v.values() for x in vs] if isinstance(v, dict) else [str(v)]
            out += [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip() for x in vals if isinstance(x, str)]
    return [x for x in out if x]


def item_creators(meta: list) -> list[str]:
    """The image record's Creator and Contributor values for this item. Archive records also list the
    whole collection's creator ('From the Collection: Kissinger, Henry...'); that isn't this item's maker."""
    return [x for x in metadata_values(meta, "Creator") + metadata_values(meta, "Contributor")
            if not x.lower().startswith("from the collection")]


def fill_from_manifest(r: dict, m: dict | None) -> None:
    """Fill a row's missing date, creator and descriptive notes from its IIIF manifest (the Library's own
    image record). Only empty fields are filled."""
    meta = (m or {}).get("metadata")
    if not r.get("date_latest_year"):
        display, y0, y1 = manifest_date(m)
        if display or y0:
            r.update(date_display=r.get("date_display") or display, date_earliest_year=y0, date_latest_year=y1,
                     date_kind=r.get("date_kind") or "from the image record")
    if not r.get("creators") or r.get("creator_source") == "image record":
        who = item_creators(meta)
        r.update(creators=" | ".join(who), creator_names="", creator_roles="", creator_source="image record" if who else "")
        r.pop("_creators_raw", None)
        r.pop("_creator_roles_raw", None)
    notes = {k: v for k in ("Abstract", "Description", "Alternative Text") if (v := metadata_value(meta, k))}
    if notes and not r.get("_manifest_notes"):
        r["_manifest_notes"] = notes


def cmd_relabel(args):
    """Re-derive rights and dates in an existing folder of results and rewrite its files. With
    --fill-from-manifests, rows missing a date, creator or notes get them from their IIIF manifest
    (the museums' IIIF servers only, never LUX)."""
    folder = Path(args.folder).resolve()
    museums = load_museums()
    client = Client(min_interval=1.0) if args.fill_from_manifests else None
    for m in museums:
        p = folder / f"{m['slug']}.json"
        if not p.exists():
            continue
        rows = json.loads(p.read_text(encoding="utf-8"))
        if client and (not args.museum or m["slug"] in args.museum):
            for r in rows:
                missing = (not r.get("date_latest_year") or not r.get("creators") or not r.get("_manifest_notes")
                           or r.get("creator_source") == "image record")
                if missing and r.get("iiif_manifest_url") and "lux.collections" not in r["iiif_manifest_url"]:
                    fill_from_manifest(r, client.get_json(r["iiif_manifest_url"]))
        rows = [normalize(r) for r in rows]
        write_outputs(rows, folder, m["slug"])
        print(f"  {m['slug']}: {sum(r['image_usable'] == 'yes' for r in rows)}/{len(rows)} images usable")
    print(f"all_museums: {write_combined(folder, [m['slug'] for m in museums])} records")


def cmd_report(args):
    folder = Path(args.folder).resolve()
    units = json.loads((DATA / "units.json").read_text(encoding="utf-8"))
    museums = units["museums"]
    data = {}
    for m in museums:
        p = folder / f"{m['slug']}.json"
        if p.exists():
            data[m["slug"]] = [normalize(r) for r in json.loads(p.read_text(encoding="utf-8"))]
    title = args.title or f"LUX data report ({folder.name})"
    L = [f"# {title}", "",
         f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by `harvest/lux_harvest.py report {folder.relative_to(ROOT) if folder.is_relative_to(ROOT) else folder}`. "
         f"Counts checked against LUX on {units['checked_at'][:10]}.", ""]

    L += ["## 1. Holding units LUX uses", "",
          f"LUX holds **{units['total_objects_in_lux']:,}** physical objects (`recordType: HumanMadeObject`). "
          "Every object belongs to one of these holding units (LUX's *Responsible Units* facet):", "",
          "| Holding unit | Physical objects | All record types | Departments / collections |", "|---|---:|---:|---|"]
    for u in units["units"]:
        depts = "; ".join(f"{d['label'].split(',')[0]} ({d['objects']:,})" for d in u["departments"][:20])
        L.append(f"| {u['display_name']} | {u['objects']:,} | {u['all_record_types']:,} | {depts} |")

    L += ["", "## 2. Objects per museum", "",
          "| Museum | Slug | All objects | With digital image | On view (estimate) | Records in this folder | Mapping |",
          "|---|---|---:|---:|---:|---:|---|"]
    for m in museums:
        rows = data.get(m["slug"], [])
        version = "" if not rows else ("current" if "creator_source" in rows[0] else "first pass*")
        L.append(f"| {m['label']} | `{m['slug']}` | {m['count_all']:,} | {m['count_images']:,} | "
                 f"{m['count_on_view_estimate']:,} | {len(rows):,} | {version} |")
    if any(rows and "creator_source" not in rows[0] for rows in data.values()):
        L += ["", "\\* Fetched with the first version of the field mapping, before resolved creator/collector "
              "names, `creator_source`, `other_identifiers` and linked-work lookups for library items were added. "
              "Those columns show – below. Rights categories and dates are re-derived for them, so sections 4 and 5 "
              "are comparable. `sample --resume` brings them up to date."]

    rows_all = [r for rows in data.values() for r in rows]
    L += ["", "## 3. Field coverage (% of records with a value)", "",
          "| Field | " + " | ".join(f"`{s}`" for s in data) + " | All |",
          "|---|" + "---:|" * (len(data) + 1)]
    for fld in REPORT_FIELDS:
        cells = [pct(sum(1 for r in rows if str(r.get(fld, "")).strip()), len(rows))
                 if any(fld in r for r in rows) else "–" for rows in data.values()]
        has = [r for r in rows_all if fld in r]
        allc = pct(sum(1 for r in has if str(r.get(fld, "")).strip()), len(has))
        L.append(f"| {fld} | " + " | ".join(cells) + f" | {allc} |")
    missing = Counter(f for r in rows_all for f in REPORT_FIELDS if f in r and not str(r.get(f, "")).strip())
    L += ["", "Empty values across all records: " +
          ", ".join(f"{f} {n}" for f, n in missing.most_common()) + ".", ""]

    L += ["## 4. Image rights", "",
          "An image is marked **usable** (`image_usable = yes`) only when the rights statement for the image "
          "is CC0, public domain, or *No Copyright – United States* (the rightsstatements.org label for works "
          "in the US public domain), and the object's own copyright statement doesn't contradict it. "
          f"Yale University Library objects made before {OPEN_ACCESS_BEFORE} are also usable under Yale's Open "
          "Access policy when the Library's statement is only the generic \"may be subject to copyright\" line "
          f"(category *{OPEN_ACCESS_CATEGORY}*). "
          "Everything else is flagged with a reason in `image_flag_reason`.", "",
          "| Museum | " + " | ".join(sorted({r['image_rights_category'] for r in rows_all})) + " | Usable |",
          "|---|" + "---:|" * (len({r['image_rights_category'] for r in rows_all}) + 1)]
    cats = sorted({r["image_rights_category"] for r in rows_all})
    for slug, rows in data.items():
        c = Counter(r["image_rights_category"] for r in rows)
        L.append(f"| `{slug}` | " + " | ".join(str(c.get(k, 0)) for k in cats) +
                 f" | {sum(r['image_usable'] == 'yes' for r in rows)}/{len(rows)} |")
    c = Counter(r["image_rights_category"] for r in rows_all)
    L.append("| **All** | " + " | ".join(f"**{c.get(k, 0)}**" for k in cats) +
             f" | **{sum(r['image_usable'] == 'yes' for r in rows_all)}/{len(rows_all)}** |")
    stmts = Counter((r["image_rights_level"], r["image_rights_statement"][:140]) for r in rows_all)
    L += ["", "Exact statements seen (level → text):", ""]
    L += [f"- `{lvl or 'none'}` × {n}: {s or '(empty)'}" for (lvl, s), n in stmts.most_common()]
    flags = Counter(r["image_flag_reason"] for r in rows_all if r["image_flag_reason"])
    L += ["", "Flag reasons: " + "; ".join(f"{k} ({n})" for k, n in flags.most_common()) + ".", ""]

    # Automatic oddity checks (grouped by museum, so each line reads "what x how many")
    odd = []
    for r in rows_all:
        g = r["harvest_group"]
        if r["title"].strip().lower() in {"untitled", "[untitled]", ""}:
            odd.append(f"Untitled object ({g})")
        if r["date_earliest_year"] and r["date_latest_year"] and int(r["date_earliest_year"]) > int(r["date_latest_year"]):
            odd.append(f"Earliest year after latest year ({g})")
        if r["accession_number"] and r["accession_number_type"] == "":
            odd.append(f"Object number has no type label in LUX ({g})")
        if r.get("image_count") and int(r["image_count"] or 0) > 50:
            odd.append(f"More than 50 images in one manifest, e.g. every page of a book ({g})")
        if not r["accession_number"] and r.get("other_identifiers"):
            odd.append(f"No accession number, only system-assigned numbers ({g})")
        if r["date_display"].lower() in ("n.d.", "undated") and r["date_earliest_year"]:
            odd.append(f"Display date says '{r['date_display']}' but LUX gives a year range ({g})")
        if r["image_usable"] == "no" and r["date_latest_year"] and int(r["date_latest_year"]) < 1900 \
                and r["image_rights_category"] != "No image":
            odd.append(f"Made before 1900 but image flagged: {r['image_rights_category']} ({g})")
        if r["image_rights_category"] == OPEN_ACCESS_CATEGORY:
            odd.append(f"Usable under Yale's Open Access policy, made before {OPEN_ACCESS_BEFORE} ({g})")
        elif r["image_usable"] == "yes" and r["image_rights_level"] == "manifest":
            odd.append(f"Usable on the strength of a manifest-level licence, not an image-level one ({g})")
    oc = Counter(odd)
    L += ["## 5. Automatic checks", ""] + ([f"- {o}" + (f" × {n}" if n > 1 else "") for o, n in sorted(oc.items())]
                                           or ["- Nothing unusual."]) + [""]
    (OUTPUT).mkdir(parents=True, exist_ok=True)
    out = Path(args.output) if args.output else OUTPUT / f"lux_report_{folder.name}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Saved {out}")
    if args.html:
        html_path = Path(args.html).resolve()
        local = cache_thumbnails(Client(), data, html_path.parent) if args.local_thumbs else {}
        html_path.write_text(preview_html(title, museums, data, local), encoding="utf-8")
        print(f"Saved {args.html}")


THUMBS = DATA / "thumbs"                                # local thumbnail copies for previews (not in git)


def cache_thumbnails(client: Client, data: dict[str, list[dict]], html_dir: Path) -> dict[str, str]:
    """Download each record's thumbnail once (same polite client: 1 request/s, retries), so previews
    work offline. Returns thumbnail URL -> path relative to the HTML file."""
    import hashlib
    THUMBS.mkdir(parents=True, exist_ok=True)
    out = {}
    urls = sorted({r["thumbnail_url"] for rows in data.values() for r in rows if r.get("thumbnail_url")})
    for i, url in enumerate(urls, 1):
        path = THUMBS / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".jpg")
        if not path.exists():
            client._wait()
            client.stats["requests"] += 1
            try:
                r = client.session.get(url, timeout=60, headers={"Accept": "image/*"})
            except requests.RequestException as exc:
                print(f"  thumbnail failed ({type(exc).__name__}): {url}", file=sys.stderr)
                continue
            if r.status_code != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
                print(f"  thumbnail HTTP {r.status_code}: {url}", file=sys.stderr)
                continue
            path.write_bytes(r.content)
            print(f"  thumbnails {i}/{len(urls)}", end="\r")
        out[url] = os.path.relpath(path, html_dir)
    print(f"  {len(out)}/{len(urls)} thumbnails cached in {THUMBS}")
    return out


def preview_html(title: str, museums: list[dict], data: dict[str, list[dict]],
                 local: dict[str, str] | None = None) -> str:
    """A black-and-pink page of record cards (thumbnails load from Yale's image server)."""
    from html import escape as e
    labels_by_slug = {m["slug"]: m["label"] for m in museums}
    sections = []
    for slug, rows in data.items():
        cards = []
        for r in rows:
            src = (local or {}).get(r["thumbnail_url"], r["thumbnail_url"])
            img = (f'<img loading="lazy" src="{e(src)}" alt="{e(r["alt_text"][:200] or r["title"])}">'
                   if r["thumbnail_url"] else '<div class="noimg">no image</div>')
            ok = r["image_usable"] == "yes"
            facts = [r["creators"], r["date_display"], r["object_type"] or r["classification"], r["medium"]]
            cards.append(
                f'<article>{img}<div class="body"><span class="badge {"ok" if ok else "no"}">'
                f'{"usable" if ok else "flagged"} · {e(r["image_rights_category"])}</span>'
                f'<h3><a href="{e(r["lux_url"])}" target="_blank">{e(r["title"] or "(no title)")}</a></h3>'
                f'<p>{e(" · ".join(f for f in facts if f))}</p>'
                f'<p class="dim">{e(r["accession_number"])} · {e(r["access_statement"] or "no access statement")}</p>'
                + (f'<p class="desc">{e(r["description"][:220])}</p>' if r["description"] else "")
                + "</div></article>")
        sections.append(f'<h2>{e(labels_by_slug.get(slug, slug))} <small>{len(rows)} records</small></h2>'
                        f'<div class="grid">{"".join(cards)}</div>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(title)}</title>
<style>
 body{{background:#0b0b0d;color:#f5e9f0;font:15px/1.45 system-ui,sans-serif;margin:0;padding:28px 40px}}
 h1{{color:#ff5fa2;margin:0 0 4px}} h2{{color:#ff8cc0;border-bottom:1px solid #3a2030;padding-bottom:6px;margin-top:40px}}
 h2 small{{color:#a98a9a;font-weight:400;font-size:14px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:16px}}
 article{{background:#17121a;border:1px solid #3a2030;border-radius:12px;overflow:hidden}}
 article img,.noimg{{width:100%;height:180px;object-fit:contain;background:#000;display:block}}
 .noimg{{display:flex;align-items:center;justify-content:center;color:#6d5664}}
 .body{{padding:10px 12px}} h3{{font-size:15px;margin:6px 0}} a{{color:#ffd1e6}}
 p{{margin:4px 0;font-size:13px}} .dim{{color:#a98a9a}} .desc{{color:#e8cfdc}}
 .badge{{font-size:11px;padding:2px 8px;border-radius:999px;display:inline-block}}
 .ok{{background:#ff5fa2;color:#0b0b0d}} .no{{background:#3a2030;color:#ffb3d4}}
</style></head><body><h1>{e(title)}</h1>
<p class="dim">Pink badge = image usable (public domain / CC0). Dark badge = flagged. Click a title to open it in LUX.</p>
{"".join(sections)}</body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between requests (default 1.0)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("discover", help="find holding units, departments and counts")
    s = sub.add_parser("sample", help="fetch N records per museum")
    s.add_argument("--n", type=int, default=20)
    s.add_argument("--scope", choices=["all", "images", "on_view"], default="images")
    s.add_argument("--museum", nargs="*", help="museum slugs (default: all)")
    s.add_argument("--out", default=str(DATA / "samples"))
    s.add_argument("--resume", action="store_true", help="skip museums already sampled (rebuild them from the raw cache)")
    h = sub.add_parser("harvest", help="full resumable harvest")
    h.add_argument("--scope", choices=["all", "images", "on_view"], required=True)
    h.add_argument("--museum", nargs="*", help="museum slugs (default: all)")
    h.add_argument("--limit", type=int, help="stop after N records per museum (for testing)")
    h.add_argument("--out", default=str(DATA / "full"))
    rl = sub.add_parser("relabel", help="re-derive rights/dates in a folder of results and rewrite it")
    rl.add_argument("folder")
    rl.add_argument("--fill-from-manifests", action="store_true",
                    help="fill missing date, creator and notes from IIIF manifests (not LUX)")
    rl.add_argument("--museum", nargs="*", help="only these museums for --fill-from-manifests")
    rm = sub.add_parser("remap", help="rebuild outputs from the raw cache (no refetching)")
    rm.add_argument("which", choices=["samples", "full"])
    rm.add_argument("--museum", nargs="*", help="museum slugs (default: all)")
    r = sub.add_parser("report", help="write the coverage + rights report for a folder of results")
    r.add_argument("folder")
    r.add_argument("--output")
    r.add_argument("--title")
    r.add_argument("--html", help="also write an HTML preview of the records to this path")
    r.add_argument("--local-thumbs", action="store_true",
                   help="download thumbnails to data/lux/thumbs/ so the preview works offline")
    args = ap.parse_args()

    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "relabel":
        return cmd_relabel(args)
    client = Client(min_interval=max(1.0, args.interval))
    try:
        {"discover": cmd_discover, "sample": cmd_sample, "harvest": cmd_harvest,
         "remap": cmd_remap}[args.cmd](client, args)
    except KeyboardInterrupt:
        print("\nStopped. Rerun the same command to resume.")
        sys.exit(130)
    except Blocked as exc:
        print(f"\nStopped: {exc}. LUX is rate-limiting this address. Wait an hour, then rerun the "
              f"same command (it resumes) with a slower --interval, e.g. --interval 2.")
        sys.exit(2)


if __name__ == "__main__":
    main()
