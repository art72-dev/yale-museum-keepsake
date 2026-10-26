"""Object images, served through our backend.

- Rights are enforced here, not just in the UI: only images whose rights statement is public domain or
  CC0 (`image_usable == "yes"` from the harvester) are ever fetched or served.
- Each image is downloaded from Yale's servers once, then served from data/lux/thumbs/ (small) or
  data/lux/images/ (print size). Both folders stay out of git.
- Upstream requests are spaced out (one at a time, at most 2 per second).
"""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

import requests

from catalog import ROOT

THUMBS = ROOT / "data" / "lux" / "thumbs"          # same cache the harvester's preview uses
LARGE = ROOT / "data" / "lux" / "images"
USER_AGENT = "YaleMuseumKeepsake/0.1 (Yale SOM MGT 409 student project)"
PRINT_SIZE = "!1600,1600"                           # IIIF: fit inside 1600 x 1600 px, keep proportions

_lock = threading.Lock()
_last = 0.0
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "image/*"})


class ImageNotAllowed(Exception):
    pass


def source_url(obj: dict, size: str) -> str:
    if size == "large" and obj.get("image_service"):
        return f"{obj['image_service'].rstrip('/')}/full/{PRINT_SIZE}/0/default.jpg"   # IIIF Image API
    return obj.get("thumbnail_url") or ""


def cached_path(url: str, size: str) -> Path:
    name = hashlib.sha1(url.encode()).hexdigest()[:16] + ".jpg"
    return (LARGE if size == "large" else THUMBS) / name


def get_image(obj: dict, size: str = "thumb") -> Path:
    """Local path to the object's image, downloading it once if needed."""
    if obj.get("image_usable") != "yes":
        raise ImageNotAllowed(obj.get("image_flag_reason") or "image rights don't allow reuse")
    url = source_url(obj, size)
    if not url:
        raise FileNotFoundError("no image for this object")
    path = cached_path(url, size)
    if path.exists():
        return path
    global _last
    with _lock:                                        # one upstream download at a time, spaced out
        if path.exists():
            return path
        wait = 0.5 - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        r = _session.get(url, timeout=60)
        if r.status_code != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
            raise FileNotFoundError(f"image server answered {r.status_code}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path
