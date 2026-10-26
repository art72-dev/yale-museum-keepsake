"""Real scans (gpt-6-luna through Portkey) of the test photos in tests/scan_photos/, for the report.

Run from backend/:  ../.venv/bin/python tests/run_scan_examples.py
Writes output/scan_examples.json: what each scan read, every tool step, the outcome, and the visitor's book.
Each photo uses its own fresh test visitor, so books don't mix.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import books      # noqa: E402
import scanner    # noqa: E402
from catalog import ROOT, Catalog  # noqa: E402

EXPECT = {
    "label_violin_with_number": "added (object number on the label)",
    "label_portrait_no_number": "added (title and maker on the label)",
    "photo_oboe_no_label": "choose (no label: the visitor picks)",
    "label_not_in_sample": "not_found (that painting isn't in the test data)",
    "label_injection": "nothing added (instructions in the photo are ignored)",
}


async def main():
    cat = Catalog()
    results = []
    for photo in sorted((HERE / "scan_photos").glob("*.jpg")):
        visitor = f"scan-test-{photo.stem.replace('_', '-')}-{int(time.time())}"
        start = time.monotonic()
        r = await scanner.run_scan(cat, photo.read_bytes(), "image/jpeg", visitor)
        results.append({
            "photo": photo.name,
            "expected": EXPECT.get(photo.stem, ""),
            "status": r.status,
            "message": r.message,
            "reading": r.reading.model_dump() if r.reading else None,
            "steps": r.steps,
            "added": r.object["title"] if r.object else None,
            "candidates": [c["title"] for c in r.candidates],
            "book_after": [cat.by_id[i]["title"] for i in r.book if i in cat.by_id],
            "seconds": round(time.monotonic() - start, 1),
        })
        print(f"\n### {photo.name}  →  {r.status}   (expected: {EXPECT.get(photo.stem, '')})")
        print("  read:", r.reading.kind if r.reading else None, "|", (r.reading.title if r.reading else ""),
              "|", (r.reading.object_number if r.reading else ""))
        for s in r.steps:
            print(f"  - {s['tool']}: {s['summary']}")
        print("  message:", r.message)
        print("  book after:", results[-1]["book_after"])
        (books.BOOKS / f"{visitor}.json").unlink(missing_ok=True)   # test visitors leave no books behind
    out = ROOT / "output" / "scan_examples.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    asyncio.run(main())
