"""Data types for the blurb agent and the API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


# ---- what the agent returns -------------------------------------------------------------------

class Blurb(BaseModel):
    """One book page's text for one object, written only from its LUX fields."""

    headline: str = Field(description="A short, inviting heading for the book page (at most 10 words). "
                                      "Not just the title repeated.")
    blurb: str = Field(description="60 to 110 words for a curious visitor: what the object is, who made it, "
                                   "when, what it's made of, and one thing worth noticing. Only facts from the tools.")
    look_closer: str | None = Field(default=None,
                                    description="One sentence (under 25 words) pointing to a detail the visitor "
                                                "can see, only if a field describes it (alt text, inscription, "
                                                "medium). Otherwise null.")
    facts_used: list[str] = Field(description="Names of the fact fields the text relies on, e.g. ['title', "
                                              "'maker', 'date', 'medium'].")


# ---- per-run context --------------------------------------------------------------------------

@dataclass
class BlurbDeps:
    object_id: str
    catalog: object                                    # catalog.Catalog (kept loose to avoid an import cycle)
    facts: dict | None = None                          # a visitor-added object's details (else the catalogue's)
    source_text: str = ""                              # every fact the tools returned, for the grounding check
    warnings: list[str] = field(default_factory=list)


# ---- the scanner ------------------------------------------------------------------------------

class PhotoReading(BaseModel):
    """What the photo reader sees in a visitor's photo (text copied exactly; nothing guessed)."""

    kind: Literal["label", "artwork", "label and artwork", "unclear"] = Field(
        description="'label' = a wall label or caption card is readable; 'artwork' = an object but no readable "
                    "label; 'label and artwork' = both; 'unclear' = can't tell")
    title: str = Field("", description="The object's title exactly as printed on the label, else ''")
    maker: str = Field("", description="Artist or maker exactly as printed on the label, else ''")
    date: str = Field("", description="Date as printed on the label, else ''")
    object_number: str = Field("", description="Accession / object number as printed (e.g. '1958.59', "
                                               "'B1977.14.222', 'YPM VP 038884'), else ''")
    museum: str = Field("", description="Museum name if printed, else ''")
    keywords: str = Field("", description="3 to 6 plain words for what the object is and is made of "
                                          "(e.g. 'violin wood strings', 'clay tablet cuneiform')")
    description: str = Field(description="One sentence describing what is in the photo")


class ScanResult(BaseModel):
    """The scanner's final answer."""

    status: Literal["added", "choose", "not_found"] = Field(
        description="'added' only after add_to_book succeeded; 'choose' when the visitor should pick from "
                    "candidates; 'not_found' when nothing in the collection matches")
    object_id: str | None = Field(None, description="The object added (status 'added' only)")
    candidate_ids: list[str] = Field(default_factory=list, description="For 'choose': up to 4 candidate IDs, best first")
    message: str = Field(description="One or two friendly sentences for the visitor about what happened")


@dataclass
class ScanDeps:
    image: bytes
    media_type: str
    visitor: str
    catalog: object
    reading: PhotoReading | None = None
    candidates: dict[str, dict] = field(default_factory=dict)   # every candidate any search returned
    added: str | None = None
    blurbs: dict[str, object] = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)              # what each tool did, shown to the visitor


# ---- API --------------------------------------------------------------------------------------

class BlurbResponse(BaseModel):
    object_id: str
    headline: str
    blurb: str
    look_closer: str | None = None
    source: Literal["ai", "cache", "fallback"]
    model: str | None = None
    note: str | None = None                            # shown to the visitor when the AI text isn't available


class UsageRecord(BaseModel):
    """One line of output/usage_log.jsonl (real token counts for the report's tokenomics)."""

    time: str
    object_id: str
    model: str
    outcome: Literal["ok", "cache", "fallback", "refused_budget", "refused_rate"]
    kind: Literal["blurb", "scan"] = "blurb"
    input_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    tool_calls: int = 0
    seconds: float = 0.0
    retries: int = 0
    warnings: list[str] = []
    error: str | None = None


class ScanResponse(BaseModel):
    status: Literal["added", "choose", "not_found", "error"]
    message: str
    reading: PhotoReading | None = None
    object: dict | None = None
    blurb: BlurbResponse | None = None
    candidates: list[dict] = []
    book: list[str] = []
    steps: list[dict] = []
