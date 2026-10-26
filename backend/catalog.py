"""The collection the app shows: LUX records from data/lux/samples (test) or data/lux/full (full harvest).

Switch with KEEPSAKE_DATA in .env (a folder relative to the project root). Both folders hold the same
per-museum JSON files written by harvest/lux_harvest.py, so nothing else changes.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = "data/lux/samples"

# Research collections that aren't public galleries (photo-paper samples, a members' club library,
# a London research library with no images). Kept in the data files, hidden from visitors.
HIDDEN_GROUPS = {"lens_media_lab", "elizabethan_club", "paul_mellon_centre"}

# Statements worth showing a visitor and handing to the blurb writer (from the record's JSON extras).
CONTEXT_STATEMENTS = ("Inscription", "Inscriptions", "Signature", "Marks", "Note", "Notes", "Abstract",
                      "Summary", "Label", "Exhibitions (events)", "Linked work: Note", "Linked work: Abstract",
                      "Linked work: Attribution Statement", "Linked work: Imprint Statement")


# Visitors' words -> the museums' terms (instrument families use the Hornbostel-Sachs names).
KEYWORD_SYNONYMS = {"woodwind": "aerophone", "wind": "aerophone", "brass": "aerophone", "trumpet": "aerophone",
                    "string": "chordophone", "stringed": "chordophone", "lute": "chordophone", "guitar": "chordophone",
                    "percussion": "idiophone", "bell": "idiophone", "drum": "membranophone", "statue": "sculpture",
                    "photo": "photograph", "engraving": "print", "etching": "print", "sketch": "drawing"}

STOPWORDS = {"the", "of", "and", "a", "an", "in", "on", "at", "to", "for", "with", "from", "by", "or", "ca", "made",
              "unknown", "artist", "maker"}


def short_id(lux_uri: str) -> str:
    return lux_uri.rstrip("/").rsplit("/", 1)[-1]


def short_department(dept: str, museum: str, known: set[str] = frozenset()) -> str:
    """'European Art Collection, Yale University Art Gallery' -> 'European Art'. Library records also belong
    to archival sets ('1912', 'Everglades 1973'), so prefer a department LUX lists for the museum."""
    labels = [d for d in dept.split(" | ") if d]
    first = next((d for d in labels if d in known), labels[0] if labels else "")
    first = re.sub(r",\s*(Yale|Paul Mellon).*$", "", first).strip()
    return re.sub(r"\s+Collection(?=$|\s\()", "", first) or museum


@dataclass
class Museum:
    slug: str
    name: str
    objects: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        depts: dict[str, int] = {}
        for o in self.objects:
            depts[o["department_short"]] = depts.get(o["department_short"], 0) + 1
        return {
            "slug": self.slug,
            "name": self.name,
            "objects": len(self.objects),
            "printable_images": sum(o["image_usable"] == "yes" for o in self.objects),
            "on_view": sum(o["on_view"] == "yes" for o in self.objects),
            "departments": sorted(depts, key=lambda d: (-depts[d], d)),
            "cover_id": next((o["id"] for o in self.objects if o["image_usable"] == "yes"), None),
        }


class Catalog:
    def __init__(self, data_dir: str | None = None):
        rel = data_dir or os.getenv("KEEPSAKE_DATA", DEFAULT_DATA)
        self.data_dir = (ROOT / rel).resolve()
        units_path = ROOT / "data" / "lux" / "units.json"
        if not self.data_dir.is_dir():
            raise RuntimeError(f"Data folder not found: {self.data_dir}. See README, 'Test data vs. full data'.")
        units_doc = json.loads(units_path.read_text(encoding="utf-8")) if units_path.exists() else {}
        units = units_doc.get("museums", [])
        known = {d["label"] for u in units_doc.get("units", []) for d in u["departments"]}
        # sub-collections (Babylonian Collection, Lewis Walpole Library) belong to their parent museum
        unit_slug = {m["unit_uri"]: m["slug"] for m in units if m["kind"] == "unit"}
        self.parent = {m["slug"]: unit_slug.get(m["unit_uri"], m["slug"]) for m in units}
        self.by_id: dict[str, dict] = {}
        self.museums: dict[str, Museum] = {}
        for path in sorted(self.data_dir.glob("*.json")):
            if path.name == "all_museums.json":
                continue
            for rec in json.loads(path.read_text(encoding="utf-8")):
                if rec.get("_dropped") or rec["harvest_group"] in HIDDEN_GROUPS:
                    continue
                oid = short_id(rec["lux_uri"])
                if oid in self.by_id:
                    continue
                slug = self.parent.get(rec["harvest_group"], rec["harvest_group"])
                rec = {**rec, "id": oid, "museum_slug": slug,
                       "department_short": short_department(rec.get("department", ""), rec["holding_museum"], known)}
                self.by_id[oid] = rec
                museum = self.museums.setdefault(slug, Museum(slug, rec["holding_museum"]))
                museum.objects.append(rec)

    # ---- lists ---------------------------------------------------------------------------------

    def museum_list(self) -> list[dict]:
        return sorted((m.summary() for m in self.museums.values()), key=lambda s: -s["printable_images"])

    def search(self, museum: str | None = None, q: str = "", on_view: bool = False, printable: bool = False,
               department: str | None = None, page: int = 1, page_size: int = 24) -> dict:
        pool = self.museums[museum].objects if museum and museum in self.museums else list(self.by_id.values())
        words = [w for w in re.split(r"\s+", q.lower().strip()) if w]
        hits = []
        for o in pool:
            if on_view and o["on_view"] != "yes":
                continue
            if printable and o["image_usable"] != "yes":
                continue
            if department and o["department_short"] != department:
                continue
            if words:
                hay = " ".join(str(o.get(k, "")) for k in (
                    "title", "creators", "creator_names", "collectors", "accession_number", "department_short",
                    "object_type", "classification", "culture", "period", "medium", "date_display")).lower()
                if not all(w in hay for w in words):
                    continue
            hits.append(o)
        # objects we can show come first, then on view, then by title
        hits.sort(key=lambda o: (o["image_usable"] != "yes", o["on_view"] != "yes", o["title"].lower()))
        hidden: list[dict] = []
        if not words and not department:              # plain browsing: variety first
            hits, hidden = self._few_of_each_kind(self._mix(hits))
        start = (page - 1) * page_size
        return {"total": len(hits), "page": page, "page_size": page_size, "hidden": hidden,
                "items": [self.card(o) for o in hits[start:start + page_size]]}

    @staticmethod
    def _mix(hits: list[dict]) -> list[dict]:
        """Within each group (pictures first, then on view), take turns between departments, so one big
        department (say, 20 look-alike clay tablets) doesn't fill the whole screen."""
        out: list[dict] = []
        tiers: dict[tuple, list[dict]] = {}
        for o in hits:
            tiers.setdefault((o["image_usable"] != "yes", o["on_view"] != "yes"), []).append(o)
        for tier in tiers.values():
            groups: dict[str, list[dict]] = {}
            for o in tier:
                groups.setdefault(o["department_short"], []).append(o)
            queues = sorted(groups.values(), key=len)  # smaller departments go first in each round
            while any(queues):
                for q in queues:
                    if q:
                        out.append(q.pop(0))
        return out

    LOOKALIKES_SHOWN = 3

    @staticmethod
    def _kind(o: dict) -> str:
        """The kind of thing, from the title's first word: 'Tablet. Legal document…' -> 'tablet'."""
        words = [w.lower() for w in re.findall(r"[A-Za-z]+", o["title"])]
        words = [w for w in words if w not in ("the", "a", "an", "le", "la", "les", "untitled")]
        return words[0] if words else ""

    def _few_of_each_kind(self, hits: list[dict]) -> tuple[list[dict], list[dict]]:
        """Show at most LOOKALIKES_SHOWN of each kind per department when just browsing (three clay tablets,
        not twenty). The rest stay a tap away: the page links to the department, and search finds them all."""
        seen: dict[tuple, int] = {}
        shown, extra = [], {}
        for o in hits:
            key = (o["department_short"], self._kind(o))
            seen[key] = seen.get(key, 0) + 1
            if seen[key] <= self.LOOKALIKES_SHOWN or not key[1]:
                shown.append(o)
            else:
                extra[key] = extra.get(key, 0) + 1
        hidden = [{"department": d, "kind": k, "count": n} for (d, k), n in sorted(extra.items(), key=lambda x: -x[1])]
        return shown, hidden

    # ---- one object ----------------------------------------------------------------------------

    @staticmethod
    def maker(o: dict) -> str:
        """Who made it (never the collector of a specimen)."""
        return o.get("creator_names") or o.get("creators") or ""

    @staticmethod
    def dimensions(o: dict) -> str:
        if o.get("dimensions"):
            return o["dimensions"]
        parts = [p for p in o.get("dimensions_structured", "").split("; ") if p and "number of parts" not in p.lower()]
        return "; ".join(parts)

    def card(self, o: dict) -> dict:
        return {
            "id": o["id"],
            "title": o["title"],
            "maker": self.maker(o),
            "collected_by": "" if self.maker(o) else o.get("collectors", ""),
            "date": o["date_display"],
            "date_kind": o.get("date_kind", ""),
            "type": o["object_type"] or o["classification"].split(" | ")[0],
            "museum": o["holding_museum"],
            "museum_slug": o["museum_slug"],
            "department": o["department_short"],
            "accession_number": o["accession_number"],
            "on_view": o["on_view"] == "yes",
            "location": o["access_statement"] if o["on_view"] == "yes" else "",
            "image_usable": o["image_usable"] == "yes",
            "rights": o["image_rights_category"],
        }

    def detail(self, oid: str) -> dict | None:
        o = self.by_id.get(oid)
        if not o:
            return None
        extras = o.get("_statements", {})
        return {
            **self.card(o),
            "creators_display": o["creators"],
            "collectors": o.get("collectors", ""),
            "classification": o["classification"],
            "medium": o["medium"] or o["materials"].replace(" | ", ", "),
            "dimensions": self.dimensions(o),
            "culture": o["culture"],
            "period": o["period"],
            "description": o["description"],
            "credit_line": o["credit_line"],
            "access_statement": o["access_statement"],
            "alt_text": o["alt_text"],
            "notes": {k: v for k, v in extras.items() if k in CONTEXT_STATEMENTS},
            "image_rights_statement": o["image_rights_statement"],
            "image_flag_reason": o["image_flag_reason"],
            "object_copyright": o["object_copyright"],
            "image_count": o["image_count"],
            "museum_page_url": o["museum_page_url"],
            "lux_url": o["lux_url"],
            "iiif_manifest_url": o["iiif_manifest_url"],
        }

    def facts_for_writer(self, oid: str) -> dict | None:
        """Exactly what the blurb writer may use: LUX fields only, no URLs or rights boilerplate."""
        d = self.detail(oid)
        if not d:
            return None
        keys = ("title", "maker", "creators_display", "collectors", "date", "date_kind", "type", "classification",
                "medium", "dimensions", "culture", "period", "description", "alt_text", "notes", "credit_line",
                "museum", "department", "accession_number", "location")
        facts = {k: d[k] for k in keys if d.get(k)}
        for k, v in self.by_id[oid].get("_manifest_notes", {}).items():   # e.g. the Library's abstract of a print
            if k != "Alternative Text":
                facts.setdefault("notes", {})[f"Image record: {k}"] = [v[:900]]
        if "notes" in facts:                             # long provenance-style notes add tokens, not value
            facts["notes"] = {k: [t[:600] for t in v[:3]] for k, v in facts["notes"].items()}
        return facts

    # ---- finding a photographed object (used by the scanner's search tool) ----------------------

    @staticmethod
    def _norm_number(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    @staticmethod
    def _words(s: str) -> set[str]:
        """Lower-case words, minus stopwords, with a plural 's' removed ("instruments" -> "instrument")."""
        out = set()
        for w in re.findall(r"[a-z0-9]+", s.lower()):
            if len(w) > 1 and w not in STOPWORDS:
                out.add(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
        return out

    def find(self, title: str = "", maker: str = "", object_number: str = "", keywords: str = "",
             museum: str | None = None, limit: int = 5) -> list[dict]:
        """Candidates for what a visitor photographed, best first, each with how well it matches.

        With label text (title / maker) a candidate must share at least half the title's words or the
        maker's name; keyword-only searches (no label) match on what the object is and is made of."""
        pool = self.museums[museum].objects if museum in self.museums else list(self.by_id.values())
        want_no = self._norm_number(object_number)
        t_words, m_words = self._words(title), self._words(maker)
        k_words = self._words(keywords)
        label_search = bool(t_words or m_words)
        scored = []
        for o in pool:
            if want_no and len(want_no) >= 4 and self._norm_number(o["accession_number"]) == want_no:
                scored.append((5.0, "object number", o))
                continue
            title_hit = len(t_words & self._words(o["title"])) / len(t_words) if t_words else 0
            o_maker = self._words(self.maker(o) + " " + o.get("creators", ""))
            shared = m_words & o_maker                 # must include the label maker's longest name (the surname,
            maker_hit = bool(m_words) and len(shared) / len(m_words) >= 0.5 and max(m_words, key=len) in shared  # usually)
            if label_search:
                if title_hit < 0.5 and not maker_hit:
                    continue
                score = 2 * title_hit + (1 if maker_hit else 0)
                why = ("title and maker" if title_hit >= 0.8 and maker_hit else "title" if title_hit >= 0.8
                       else "maker and some title words" if maker_hit and title_hit else "maker" if maker_hit
                       else "some title words")
            else:
                if not k_words:
                    continue
                hay = self._words(" ".join(str(o.get(k, "")) for k in (
                    "title", "object_type", "classification", "medium", "materials", "culture", "department_short")))
                hits = sum(1 for w in k_words if w in hay or KEYWORD_SYNONYMS.get(w, "") in hay)
                kw_hit = hits / len(k_words)
                if kw_hit < 0.34:
                    continue
                score, why = kw_hit, "looks similar"
            scored.append((score, why, o))
        scored.sort(key=lambda x: (-x[0], x[2]["image_usable"] != "yes"))
        return [{**self.card(o), "match": why, "score": round(sc, 2)} for sc, why, o in scored[:limit]]

    @staticmethod
    def confident(candidate: dict) -> bool:
        """Safe to add without asking: the label's object number matched, or both title and maker did."""
        return candidate.get("match") in ("object number", "title and maker")

    def related(self, oid: str, limit: int = 3) -> list[dict]:
        """Other objects here by the same maker, else from the same department."""
        o = self.by_id.get(oid)
        if not o:
            return []
        same_maker = [x for x in self.by_id.values() if x["id"] != oid and o.get("creator_uris")
                      and set(o["creator_uris"].split(" | ")) & set(x.get("creator_uris", "").split(" | ")) - {""}]
        same_dept = [x for x in self.museums[o["museum_slug"]].objects
                     if x["id"] != oid and x["department_short"] == o["department_short"]]
        picks = (same_maker or same_dept)[:limit]
        return [{"id": x["id"], "title": x["title"], "maker": self.maker(x), "date": x["date_display"],
                 "why": "same maker" if same_maker else "same department"} for x in picks]
