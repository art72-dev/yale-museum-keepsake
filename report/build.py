"""Build the self-contained report.html and slides.html (every image embedded, no other files needed).

Edit report_src.html / slides_src.html (which point at img/...), then run from this folder:
    python3 build.py
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml"}


def inline_images(html: str) -> str:
    def repl(m: re.Match) -> str:
        path = HERE / m.group(2)
        data = base64.b64encode(path.read_bytes()).decode()
        return f'{m.group(1)}"data:{MIME[path.suffix.lower()]};base64,{data}"'
    out = re.sub(r'(src=)"(img/[^"]+)"', repl, html)
    left = re.findall(r'src="(?!data:|https?:)([^"]+)"', out)
    if left:
        raise SystemExit(f"Not embedded: {left}")
    return out


for src, dest in (("report_src.html", "report.html"), ("slides_src.html", "slides.html")):
    if (HERE / src).exists():
        html = inline_images((HERE / src).read_text(encoding="utf-8"))
        (ROOT / dest).write_text(html, encoding="utf-8")
        print(f"{dest}: {len(html) / 1e6:.1f} MB, all images embedded")
