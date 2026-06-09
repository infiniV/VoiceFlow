"""dictore://recording/<filename.wav> scheme — byte-range audio serving.

A custom `QWebEngineUrlSchemeHandler` registered in `main.py` translates each
incoming `QWebEngineUrlRequestJob` into a call to `serve_audio_range()`. That
function is the entirety of the HTTP semantics — pure, side-effect-free aside
from reading the file, and exhaustively unit-tested.

Why a custom scheme: data: URLs OOM for hour-long meetings (~460 MB encoded for
a 90-minute stereo recording). file:// URLs are unreliable in Qt WebEngine.
A custom scheme with Range support lets the HTML5 `<audio>` element seek
natively. See Q7 in the approved plan.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


SCHEME = "dictore"
RECORDING_HOST = "recording"
_RECORDINGS_DIRNAME = "recordings"


@dataclass
class AudioRangeResponse:
    status: int
    headers: dict[str, str]
    body: bytes


# ---------- URL resolution ----------

def resolve_recording_audio_url(url: str, data_root: Path) -> Optional[Path]:
    """Map a dictore:// URL to the on-disk file, rejecting anything outside
    `<data_root>/recordings/`."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return None
    if parsed.scheme != SCHEME or parsed.netloc != RECORDING_HOST:
        return None
    filename = parsed.path.lstrip("/")
    if not filename:
        return None

    recordings_root = (data_root / _RECORDINGS_DIRNAME).resolve()
    candidate = (recordings_root / filename).resolve()
    try:
        candidate.relative_to(recordings_root)
    except ValueError:
        return None
    return candidate


# ---------- byte-range serving ----------

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(header: str, size: int) -> Optional[tuple[int, int]]:
    """Parse an HTTP Range header. Returns (start, end_inclusive) or None if
    the range is malformed / unsatisfiable (caller responds 416 in that case).
    """
    m = _RANGE_RE.match(header.strip())
    if not m:
        return None
    start_raw, end_raw = m.group(1), m.group(2)
    if start_raw == "" and end_raw == "":
        return None
    if start_raw == "":
        # Suffix form: "bytes=-N" → last N bytes
        n = int(end_raw)
        if n == 0 or n > size:
            n = size
        return (size - n, size - 1)
    start = int(start_raw)
    end = int(end_raw) if end_raw else size - 1
    if start >= size or end < start:
        return None
    if end >= size:
        end = size - 1
    return (start, end)


def serve_audio_range(file_path: Path, range_header: Optional[str]) -> AudioRangeResponse:
    """Serve a WAV file with HTTP Range support so HTML5 <audio> can seek."""
    if not file_path.exists() or not file_path.is_file():
        return AudioRangeResponse(404, {"Content-Type": "text/plain"}, b"")

    size = file_path.stat().st_size

    if range_header is None:
        with file_path.open("rb") as f:
            body = f.read()
        return AudioRangeResponse(
            200,
            {
                "Content-Type": "audio/wav",
                "Content-Length": str(size),
                "Accept-Ranges": "bytes",
            },
            body,
        )

    rng = _parse_range(range_header, size)
    if rng is None:
        return AudioRangeResponse(
            416,
            {"Content-Type": "text/plain", "Content-Range": f"bytes */{size}"},
            b"",
        )
    start, end = rng
    length = end - start + 1
    with file_path.open("rb") as f:
        f.seek(start)
        body = f.read(length)
    return AudioRangeResponse(
        206,
        {
            "Content-Type": "audio/wav",
            "Content-Length": str(length),
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
        },
        body,
    )
