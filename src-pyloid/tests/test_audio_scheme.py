"""Tests for slice 8 — dictore:// audio scheme byte-range serving.

The Qt-facing wrapper (QWebEngineUrlSchemeHandler) is thin glue that translates
QWebEngineUrlRequestJob into calls to this pure function. The pure function is
exhaustively tested here; the Qt wrapper is verified by the manual end-to-end
test plan in `lets-plan-meeting-notes-ancient-gem.md`.
"""

import tempfile
from pathlib import Path

import pytest

from services.recording.audio_scheme import (
    AudioRangeResponse,
    resolve_recording_audio_url,
    serve_audio_range,
)


# ---------- URL resolution ----------

class TestResolveRecordingAudioURL:
    def test_resolves_simple_id(self, tmp_path):
        (tmp_path / "recordings").mkdir()
        (tmp_path / "recordings" / "42_x.wav").write_bytes(b"abc")
        path = resolve_recording_audio_url(
            "dictore://recording/42_x.wav", data_root=tmp_path
        )
        assert path == (tmp_path / "recordings" / "42_x.wav").resolve()

    def test_refuses_traversal(self, tmp_path):
        """A path that resolves outside the recordings dir must return None."""
        # Try to escape via "../"
        outside = tmp_path.parent / "evil.txt"
        outside.write_text("nope")
        path = resolve_recording_audio_url(
            "dictore://recording/../evil.txt", data_root=tmp_path
        )
        assert path is None

    def test_refuses_non_dictore_scheme(self, tmp_path):
        assert resolve_recording_audio_url("http://recording/x.wav", data_root=tmp_path) is None

    def test_refuses_unknown_host(self, tmp_path):
        assert resolve_recording_audio_url("dictore://other/x.wav", data_root=tmp_path) is None


# ---------- byte-range serving ----------

@pytest.fixture
def sample_file(tmp_path):
    p = tmp_path / "x.wav"
    p.write_bytes(b"0123456789ABCDEF")  # 16 bytes
    return p


class TestServeAudioRange:
    def test_full_file_no_range_header(self, sample_file):
        resp = serve_audio_range(sample_file, range_header=None)
        assert isinstance(resp, AudioRangeResponse)
        assert resp.status == 200
        assert resp.body == b"0123456789ABCDEF"
        assert resp.headers["Content-Length"] == "16"
        assert resp.headers["Accept-Ranges"] == "bytes"
        assert resp.headers["Content-Type"] == "audio/wav"

    def test_byte_range_first_8(self, sample_file):
        resp = serve_audio_range(sample_file, range_header="bytes=0-7")
        assert resp.status == 206
        assert resp.body == b"01234567"
        assert resp.headers["Content-Range"] == "bytes 0-7/16"
        assert resp.headers["Content-Length"] == "8"

    def test_byte_range_middle(self, sample_file):
        resp = serve_audio_range(sample_file, range_header="bytes=4-11")
        assert resp.status == 206
        assert resp.body == b"456789AB"
        assert resp.headers["Content-Range"] == "bytes 4-11/16"

    def test_byte_range_open_ended(self, sample_file):
        """bytes=8- → from offset 8 to end."""
        resp = serve_audio_range(sample_file, range_header="bytes=8-")
        assert resp.status == 206
        assert resp.body == b"89ABCDEF"
        assert resp.headers["Content-Range"] == "bytes 8-15/16"

    def test_byte_range_suffix(self, sample_file):
        """bytes=-4 → last 4 bytes."""
        resp = serve_audio_range(sample_file, range_header="bytes=-4")
        assert resp.status == 206
        assert resp.body == b"CDEF"
        assert resp.headers["Content-Range"] == "bytes 12-15/16"

    def test_invalid_range_returns_416(self, sample_file):
        resp = serve_audio_range(sample_file, range_header="bytes=99-200")
        assert resp.status == 416
        assert resp.headers["Content-Range"] == "bytes */16"

    def test_malformed_range_header_returns_416(self, sample_file):
        resp = serve_audio_range(sample_file, range_header="not-a-range")
        assert resp.status == 416

    def test_missing_file_returns_404(self, tmp_path):
        resp = serve_audio_range(tmp_path / "nope.wav", range_header=None)
        assert resp.status == 404
        assert resp.body == b""

    def test_unit_other_than_bytes_returns_416(self, sample_file):
        resp = serve_audio_range(sample_file, range_header="frames=0-100")
        assert resp.status == 416
