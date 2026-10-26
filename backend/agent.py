"""The blurb writer: one PydanticAI agent (OpenAI gpt-6-luna through Portkey) with one tool.

Safety and cost, all in this file:
- Grounding check: every number and name in the text must appear in the museum's facts; otherwise the
  model gets one retry with the problems listed (see `check_grounding`).
- Limits per blurb: at most 4 model requests, 2 tool calls and 12,000 tokens.
- Cache: each object's blurb is written once (per prompt version and model) and reused for everyone.
- Daily token budget and a per-visitor rate limit. When either is hit, or the model fails, the page gets a
  plain caption built from the museum's own fields instead (`fallback`), and the visitor is told why.
- Every run is logged with its real token counts to output/usage_log.jsonl.
- Objects a visitor adds themselves (added.py) get the same writer and checks, from the details they
  typed; the text is kept with the object, not in the shared cache.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.messages import RetryPromptPart
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

import added
import tools
from catalog import ROOT, Catalog
from models import Blurb, BlurbDeps, BlurbResponse, UsageRecord

HERE = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")            # the project's own .env first ...
load_dotenv(ROOT.parent / ".env")     # ... then the folder above it (where course staff keep theirs)
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

MODEL_NAME = os.getenv("KEEPSAKE_MODEL", "gpt-6-luna")   # the only model allowed on the course key
DEFAULT_PORTKEY_URL = "https://api.portkey.ai/v1"
PROMPT = (HERE / "prompts" / "blurb.md").read_text(encoding="utf-8")
PROMPT_VERSION = hashlib.sha1(PROMPT.encode()).hexdigest()[:8]

RUN_LIMITS = UsageLimits(request_limit=4, tool_calls_limit=2, total_tokens_limit=12_000)
MAX_OUTPUT_TOKENS = 2_500        # gpt-6-luna reasons before answering; reasoning counts toward this cap
REASONING_EFFORT = os.getenv("KEEPSAKE_REASONING", "low")   # a label-writing task needs little reasoning
DAILY_TOKEN_BUDGET = int(os.getenv("KEEPSAKE_DAILY_TOKENS", "500000"))
VISITOR_LIMIT, VISITOR_WINDOW = 30, 600          # new AI blurbs per visitor per 10 minutes
MAX_PARALLEL_RUNS = 3

CACHE_PATH = ROOT / "data" / "blurb_cache.json"
USAGE_LOG = ROOT / "output" / "usage_log.jsonl"


# ---- model -------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_model() -> Model:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing: put it in .env here or in the folder above")
    provider = OpenAIProvider(api_key=api_key, base_url=os.getenv("PORTKEY_BASE_URL", DEFAULT_PORTKEY_URL))
    return OpenAIResponsesModel(MODEL_NAME, provider=provider)


def key_present() -> bool:
    return bool(os.getenv("PORTKEY_API_KEY"))


# ---- the agent ---------------------------------------------------------------------------------

blurb_agent = Agent(
    output_type=Blurb,
    deps_type=BlurbDeps,
    instructions=PROMPT,
    tools=[tools.get_object_facts],
    retries=2,
    defer_model_check=True,
    name="blurb_writer",
)

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
# Talking about the data instead of the object ("the recorded details identify the artist")
META_RE = re.compile(r"\b(?:the|these|those|recorded|given|provided|available|listed|entered) "
                     r"(?:details|information|facts|records?|fields|data)\b", re.I)
CAPITALISED_RE = re.compile(r"\b[A-Z][a-zà-ÿ'’\-]{2,}")
COMMON_WORDS = {"The", "This", "These", "Its", "It", "Yale", "University", "Museum", "Gallery", "Center", "Centre",
                "Art", "British", "Collection", "Library", "Peabody", "Look", "Find", "Notice", "See", "Made", "From",
                "With", "One", "Two", "Three", "Around", "About", "Here", "Like", "On", "In", "At", "Its", "Each",
                "Both", "Some", "Many", "Today", "During", "Between", "After", "Before", "January", "February",
                "March", "April", "May", "June", "July", "August", "September", "October", "November", "December",
                "Sr", "Jr", "Inscribed", "Signed", "Musical", "Instruments", "Morris", "Steinert", "Campus"}


def check_grounding(out: Blurb, source: str) -> tuple[list[str], list[str]]:
    """(numbers, names) in the text that the facts don't contain. Names = capitalised words that don't
    start a sentence, checked in the blurb and look-closer line (headlines may be title-cased)."""
    src = source.lower()
    text = " ".join(filter(None, [out.headline, out.blurb, out.look_closer]))
    numbers = sorted({n for n in NUMBER_RE.findall(text)
                      if n not in src and n.replace(",", "") not in src.replace(",", "")})
    names = []
    for sentence in re.split(r"(?<=[.!?])\s+", " ".join(filter(None, [out.blurb, out.look_closer]))):
        for i, m in enumerate(CAPITALISED_RE.finditer(sentence)):
            word = re.sub(r"['’]s$", "", m.group())
            if m.start() == 0 or word in COMMON_WORDS or word.lower() in src or word.lower()[:5] in src:
                continue
            names.append(word)
    return numbers, sorted(set(names))


@blurb_agent.output_validator
def validate(ctx: RunContext[BlurbDeps], out: Blurb) -> Blurb:
    if not ctx.deps.source_text:
        raise ModelRetry("Call get_object_facts first and write only from what it returns.")
    words = len(out.blurb.split())
    def send_back(reason: str):
        ctx.deps.warnings.append("retry: " + reason)     # logged, so the report can show why
        raise ModelRetry(reason)

    if not 25 <= words <= 140:
        send_back(f"The blurb has {words} words. Keep it between 35 and 110 words.")
    if re.search(r"https?://|www\.", out.blurb + (out.look_closer or "")):
        send_back("Don't include links.")
    meta = META_RE.search(" ".join(filter(None, [out.blurb, out.look_closer])))
    if meta:
        send_back(f"Write about the object, not about the facts you were given: remove \"{meta.group()}\" and "
                  "anything else about what the details say or leave out. A short page is fine.")
    numbers, names = check_grounding(out, ctx.deps.source_text)
    if numbers:
        send_back(f"These numbers aren't in the facts: {', '.join(numbers)}. Remove them or use the facts' "
                  "own wording.")
    if names:
        if ctx.retry == 0:
            send_back(f"These names or terms aren't in the facts: {', '.join(names)}. Use only names and "
                      "terms the facts contain.")
        ctx.deps.warnings.append("unverified terms kept after retry: " + ", ".join(names))
    return out


# ---- cache, usage log, budget ------------------------------------------------------------------

_cache_lock = threading.Lock()
_log_lock = threading.Lock()
_object_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_runs = asyncio.Semaphore(MAX_PARALLEL_RUNS)
_visitor_hits: dict[str, deque] = defaultdict(deque)


def _cache_key(oid: str, catalog: Catalog | None = None) -> str:
    """Changes with the model, the prompt, or the object's facts, so an improved record gets a fresh page."""
    facts = json.dumps(catalog.facts_for_writer(oid), sort_keys=True, ensure_ascii=False) if catalog else ""
    return f"{oid}|{MODEL_NAME}|{PROMPT_VERSION}|{hashlib.sha1(facts.encode()).hexdigest()[:8]}"


def plain(text: str | None) -> str | None:
    """Drop Markdown emphasis the model sometimes adds (*Title*, **bold**): the page shows text as-is."""
    if text is None:
        return None
    return re.sub(r"(\*{1,2})(?=\S)(.+?)(?<=\S)\1", r"\2", text)


def _load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}


def _save_to_cache(key: str, blurb: Blurb):
    with _cache_lock:
        cache = _load_cache()
        cache[key] = blurb.model_dump()
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(CACHE_PATH)


def log_usage(rec: UsageRecord):
    with _log_lock:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(USAGE_LOG, "a", encoding="utf-8") as f:
            f.write(rec.model_dump_json() + "\n")


def tokens_spent_today() -> int:
    if not USAGE_LOG.exists():
        return 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = 0
    with open(USAGE_LOG, encoding="utf-8") as f:
        for line in f:
            if line.startswith('{"time":"' + today):
                r = json.loads(line)
                total += r["input_tokens"] + r["output_tokens"]
    return total


def _visitor_allowed(visitor: str) -> bool:
    hits, now = _visitor_hits[visitor], time.monotonic()
    while hits and now - hits[0] > VISITOR_WINDOW:
        hits.popleft()
    if len(hits) >= VISITOR_LIMIT:
        return False
    hits.append(now)
    return True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- fallback caption --------------------------------------------------------------------------

def fallback_caption(catalog: Catalog, oid: str, note: str) -> BlurbResponse:
    """The museum's own details as a sentence or two. Nothing is generated."""
    d = catalog.detail(oid) or {}
    who = re.sub(r"\b(Artist|Maker|Manufacturer|Primary Artist):\s*(\(Made by\)\s*)?", "", d.get("maker", ""))
    who = "" if who.strip().lower() in ("unknown", "") else who.replace(" | ", ", ")
    first = d.get("title", "").rstrip(".")
    if who:
        first += f", by {who}"
    if d.get("date") and d.get("date_kind") != "collected":
        first += f", {d['date']}"
    parts = [first.rstrip(".") + "."]
    if d.get("medium"):
        parts.append(d["medium"][0].upper() + d["medium"][1:].rstrip(".") + ".")
    if d.get("collected_by"):
        parts.append(f"Collected by {d['collected_by'].replace(' | ', ', ')}"
                     + (f", {d['date']}." if d.get("date") else "."))
    parts.append(f"{d.get('department', '')}, {d.get('museum', '')}.".lstrip(", "))
    return BlurbResponse(object_id=oid, headline=d.get("title", ""), blurb=" ".join(parts),
                         source="fallback", model=None, note=note)


# ---- running the writer ------------------------------------------------------------------------

TASK = "Write the keepsake-book page for this object."
ADDED_TASK = ("Write the keepsake-book page for this object. The visitor typed these facts in themselves (from the "
              "wall label and what they saw); they are not the museum's record. Use only them, and don't say the "
              "museum describes or records anything. Visitors often give only a few details: then write a short page "
              "of two or three sentences (30 to 60 words) from what is there. Don't describe how the object looks "
              "unless the label text or materials say so, and never comment on what the details include or leave out.")
ADDED_VERSION = hashlib.sha1((PROMPT + ADDED_TASK).encode()).hexdigest()[:8]

REFUSALS = {
    "budget": "Today's AI budget is used up, so this page shows {whose} details. The written description will be "
              "back tomorrow.",
    "rate": "You've asked for a lot of descriptions in a few minutes. This page shows {whose} details; try again "
            "shortly.",
    "no_key": "The AI writer isn't set up on this server (no API key), so this page shows {whose} details.",
    "failed": "The AI description couldn't be written for this object, so this page shows {whose} details.",
}


def _refusal(oid: str, visitor: str, model: Model | None) -> str | None:
    """Why the AI shouldn't run now (a REFUSALS key), or None. Refusals are logged."""
    if tokens_spent_today() >= DAILY_TOKEN_BUDGET:
        log_usage(UsageRecord(time=_now(), object_id=oid, model=MODEL_NAME, outcome="refused_budget"))
        return "budget"
    if not _visitor_allowed(visitor):
        log_usage(UsageRecord(time=_now(), object_id=oid, model=MODEL_NAME, outcome="refused_rate"))
        return "rate"
    if model is None and not key_present():
        return "no_key"
    return None


async def _write(deps: BlurbDeps, task: str, model: Model | None) -> Blurb | None:
    """One run of the writer, logged with its real token counts. None if it failed."""
    start = time.monotonic()
    rec = UsageRecord(time=_now(), object_id=deps.object_id, model=MODEL_NAME, outcome="ok")
    async with _runs:
        try:
            result = await blurb_agent.run(
                task, deps=deps, model=model or get_model(), usage_limits=RUN_LIMITS,
                model_settings=OpenAIResponsesModelSettings(max_tokens=MAX_OUTPUT_TOKENS, timeout=60,
                                                            openai_reasoning_effort=REASONING_EFFORT))
        except Exception as exc:                      # limits, model errors, content filter, network
            rec.outcome, rec.error = "fallback", f"{type(exc).__name__}: {str(exc)[:300]}"
            rec.seconds = round(time.monotonic() - start, 2)
            log_usage(rec)
            return None
    u = result.usage
    rec.input_tokens, rec.cache_read_tokens, rec.output_tokens = u.input_tokens, u.cache_read_tokens, u.output_tokens
    rec.requests, rec.tool_calls = u.requests, u.tool_calls
    rec.retries = sum(isinstance(p, RetryPromptPart) for m in result.all_messages() for p in getattr(m, "parts", []))
    rec.seconds, rec.warnings = round(time.monotonic() - start, 2), deps.warnings
    log_usage(rec)
    out: Blurb = result.output
    return out.model_copy(update={k: plain(getattr(out, k)) for k in ("headline", "blurb", "look_closer")})


def _from_cache(oid: str, b: dict) -> BlurbResponse:
    return BlurbResponse(object_id=oid, source="cache", model=MODEL_NAME,
                         **{k: plain(b[k]) for k in ("headline", "blurb", "look_closer")})


# ---- the entry points --------------------------------------------------------------------------

async def get_blurb(catalog: Catalog, oid: str, visitor: str = "anon", model: Model | None = None) -> BlurbResponse:
    if oid not in catalog.by_id:
        raise KeyError(oid)
    key = _cache_key(oid, catalog)
    cached = _load_cache().get(key)
    if cached:
        log_usage(UsageRecord(time=_now(), object_id=oid, model=MODEL_NAME, outcome="cache"))
        return _from_cache(oid, cached)

    async with _object_locks[oid]:                     # two visitors saving the same object: write it once
        cached = _load_cache().get(key)
        if cached:
            return _from_cache(oid, cached)
        reason = _refusal(oid, visitor, model)
        if reason:
            return fallback_caption(catalog, oid, REFUSALS[reason].format(whose="the museum's own"))
        out = await _write(BlurbDeps(object_id=oid, catalog=catalog), TASK, model)
        if out is None:
            return fallback_caption(catalog, oid, REFUSALS["failed"].format(whose="the museum's own"))
        _save_to_cache(key, out)
        return BlurbResponse(object_id=oid, headline=out.headline, blurb=out.blurb, look_closer=out.look_closer,
                             source="ai", model=MODEL_NAME)


def added_caption(rec: dict, museum_name: str, note: str) -> BlurbResponse:
    """A visitor-added object's own details as a sentence or two. Nothing is generated."""
    first = rec["title"].rstrip(".")
    if rec["maker"].strip().lower() not in ("unknown", ""):
        first += f", by {rec['maker']}"
    parts = [f"{first}, {rec['date']}."]
    if rec["medium"]:
        parts.append(rec["medium"][0].upper() + rec["medium"][1:].rstrip(".") + ".")
    parts.append(f"{rec['department']}, {museum_name}.".lstrip(", "))
    return BlurbResponse(object_id=rec["id"], headline=rec["title"], blurb=" ".join(parts), source="fallback",
                         model=None, note=note)


async def get_added_blurb(catalog: Catalog, visitor: str, oid: str, model: Model | None = None) -> BlurbResponse:
    """The page text for an object the visitor added: written only from what they typed, kept with the object."""
    rec = added.get(visitor, oid)
    if rec is None:
        raise KeyError(oid)
    museum = catalog.museums[rec["museum"]].name if rec["museum"] in catalog.museums else rec["museum"]
    facts = added.facts(rec, museum)
    key = f"{MODEL_NAME}|{ADDED_VERSION}|{hashlib.sha1(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:8]}"
    if rec.get("blurb") and rec.get("blurb_key") == key:
        log_usage(UsageRecord(time=_now(), object_id=oid, model=MODEL_NAME, outcome="cache"))
        return _from_cache(oid, rec["blurb"])

    async with _object_locks[f"{visitor}/{oid}"]:
        rec = added.get(visitor, oid) or rec
        if rec.get("blurb") and rec.get("blurb_key") == key:
            return _from_cache(oid, rec["blurb"])
        reason = _refusal(oid, visitor, model)
        if reason:
            return added_caption(rec, museum, REFUSALS[reason].format(whose="your own"))
        out = await _write(BlurbDeps(object_id=oid, catalog=catalog, facts=facts), ADDED_TASK, model)
        if out is None:
            return added_caption(rec, museum, REFUSALS["failed"].format(whose="your own"))
        added.save_blurb(visitor, oid, key, out.model_dump())
        return BlurbResponse(object_id=oid, headline=out.headline, blurb=out.blurb, look_closer=out.look_closer,
                             source="ai", model=MODEL_NAME)
