"""The scanner: a visitor's photo -> the object in the collection -> its book page -> added to their book.

Two agents here, plus the description writer from agent.py:
- **Scanner** (orchestrator, text only): tools read_photo, search_collection, write_blurb, add_to_book.
- **Photo reader** (vision): called by read_photo; copies label text and describes the object.
- **Description writer** (agent.py): called by write_blurb; cached, grounded in the museum's record.

Guards: add_to_book only adds a confident match returned by this scan's own search, at most one per scan;
the final answer can't claim an add that didn't happen; per-scan limits; per-visitor scan rate; the
shared daily token budget. Every scan is logged with its real token counts.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from pathlib import Path

from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModelSettings
from pydantic_ai.usage import RunUsage, UsageLimits

import agent as writer
import books
import tools
from catalog import Catalog
from models import PhotoReading, ScanDeps, ScanResponse, ScanResult, UsageRecord

HERE = Path(__file__).resolve().parent
SCAN_LIMITS = UsageLimits(request_limit=10, tool_calls_limit=10, total_tokens_limit=40_000)
SETTINGS = OpenAIResponsesModelSettings(max_tokens=2_500, timeout=60, openai_reasoning_effort=writer.REASONING_EFFORT)
SCANS_PER_VISITOR, SCAN_WINDOW = 12, 600              # scans per visitor per 10 minutes

photo_reader = Agent(
    output_type=PhotoReading,
    instructions=(HERE / "prompts" / "photo_reader.md").read_text(encoding="utf-8"),
    retries=1,
    defer_model_check=True,
    name="photo_reader",
)

scanner_agent = Agent(
    output_type=ScanResult,
    deps_type=ScanDeps,
    instructions=(HERE / "prompts" / "scanner.md").read_text(encoding="utf-8"),
    tools=[tools.read_photo, tools.search_collection, tools.write_blurb, tools.add_to_book],
    retries=2,
    defer_model_check=True,
    name="scanner",
)

_model_override: Model | None = None                  # tests swap in a scripted model
_scan_hits: dict[str, deque] = defaultdict(deque)


async def read_image(image: bytes, media_type: str, usage: RunUsage) -> PhotoReading:
    """Run the photo reader on the image (high detail, so small label text is legible)."""
    result = await photo_reader.run(
        ["Read this photo.", BinaryContent(data=image, media_type=media_type, vendor_metadata={"detail": "high"})],
        model=_model_override or writer.get_model(), model_settings=SETTINGS, usage=usage,
        usage_limits=UsageLimits(request_limit=3, total_tokens_limit=15_000))
    return result.output


def _rate_ok(visitor: str) -> bool:
    hits, now = _scan_hits[visitor], time.monotonic()
    while hits and now - hits[0] > SCAN_WINDOW:
        hits.popleft()
    if len(hits) >= SCANS_PER_VISITOR:
        return False
    hits.append(now)
    return True


async def run_scan(catalog: Catalog, image: bytes, media_type: str, visitor: str) -> ScanResponse:
    if writer.tokens_spent_today() >= writer.DAILY_TOKEN_BUDGET:
        return ScanResponse(status="error", message="Scanning is resting for today (the AI budget is used up). "
                                                    "You can still search and save objects by hand.")
    if not _rate_ok(visitor):
        return ScanResponse(status="error", message="That's a lot of scans in a few minutes. Try again shortly.")
    if _model_override is None and not writer.key_present():
        return ScanResponse(status="error", message="Scanning isn't set up on this server (no API key).")

    deps = ScanDeps(image=image, media_type=media_type, visitor=visitor, catalog=catalog)
    rec = UsageRecord(time=writer._now(), object_id="scan", model=writer.MODEL_NAME, outcome="ok", kind="scan")
    start = time.monotonic()
    try:
        result = await scanner_agent.run("A visitor just took this photo.", deps=deps,
                                         model=_model_override or writer.get_model(),
                                         model_settings=SETTINGS, usage_limits=SCAN_LIMITS)
    except Exception as exc:
        rec.outcome, rec.error = "fallback", f"{type(exc).__name__}: {str(exc)[:300]}"
        rec.seconds = round(time.monotonic() - start, 2)
        writer.log_usage(rec)
        return ScanResponse(status="error", message="Sorry, I couldn't read that photo. Try again, closer to the label.",
                            reading=deps.reading, steps=deps.steps, book=books.get_book(visitor))

    out: ScanResult = result.output
    u = result.usage
    rec.input_tokens, rec.cache_read_tokens, rec.output_tokens = u.input_tokens, u.cache_read_tokens, u.output_tokens
    rec.requests, rec.tool_calls, rec.seconds = u.requests, u.tool_calls, round(time.monotonic() - start, 2)
    rec.object_id = deps.added or "scan"

    # The tools' effects are the truth, not the model's claim about them.
    status, message = out.status, writer.plain(out.message)
    if status == "added" and not deps.added:
        status, message = "choose", "I couldn't be sure which object this is. Is it one of these?"
        rec.warnings.append("model claimed an add that didn't happen; downgraded to choose")
    if deps.added:
        status = "added"
    rec.warnings.extend(s["summary"] for s in deps.steps if s["summary"].startswith("Refused"))
    writer.log_usage(rec)

    resp = ScanResponse(status=status, message=message, reading=deps.reading, steps=deps.steps,
                        book=books.get_book(visitor))
    if status == "added":
        resp.object = catalog.card(catalog.by_id[deps.added])
        resp.blurb = deps.blurbs.get(deps.added)
    else:
        ids = [i for i in out.candidate_ids if i in deps.candidates] or list(deps.candidates)[:4]
        r = deps.reading
        if r and (r.title or r.object_number) and all(deps.candidates[i]["match"] == "looks similar" for i in ids):
            ids = []                                   # a label was read: look-alikes would be guesses
        resp.candidates = [catalog.card(catalog.by_id[i]) for i in ids[:4] if i in catalog.by_id]
        if status == "choose" and not resp.candidates:
            resp.status = "not_found"
            if out.status == "choose":
                resp.message = "I could read the label, but that object isn't in this app's collection yet."
    return resp
