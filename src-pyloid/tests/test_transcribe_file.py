"""Tests for slice 7 — TranscriptionService.transcribe_file + CancelToken.

The Whisper model is mocked so these tests are fast and deterministic. A real
transcription test would belong in a slow integration suite gated by
`DICTORE_BIG_MODEL_TESTS=1`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.transcription import (
    CancelToken,
    TranscriptionCancelled,
    TranscriptionService,
)


# ---------- CancelToken ----------

class TestCancelToken:
    def test_default_not_cancelled(self):
        t = CancelToken()
        assert t.is_cancelled is False

    def test_cancel_sets_flag(self):
        t = CancelToken()
        t.cancel()
        assert t.is_cancelled is True

    def test_cancel_is_idempotent(self):
        t = CancelToken()
        t.cancel()
        t.cancel()
        assert t.is_cancelled is True


# ---------- transcribe_file ----------

class _FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class _FakeWhisperModel:
    """Stand-in for faster_whisper.WhisperModel.

    Records the kwargs it received so tests can assert on language/vad config.
    Yields the segments it was constructed with.
    """

    def __init__(self, segments, duration=10.0):
        self._segments = list(segments)
        self._duration = duration
        self.last_kwargs: dict = {}

    def transcribe(self, audio, **kwargs):
        self.last_kwargs = {"audio": audio, **kwargs}
        info = SimpleNamespace(duration=self._duration, language="en")
        return iter(self._segments), info


@pytest.fixture
def loaded_service(tmp_path):
    svc = TranscriptionService()
    svc._model = _FakeWhisperModel(
        segments=[
            _FakeSegment(0.0, 1.0, " hello"),
            _FakeSegment(1.0, 2.5, " world"),
        ],
        duration=2.5,
    )
    svc._current_model_name = "fake"
    svc._current_device = "cpu"
    # Provide a file path; the fake model never reads it.
    fixture = tmp_path / "fake.wav"
    fixture.write_bytes(b"RIFF")  # presence is enough; mock ignores content
    return svc, fixture


class TestTranscribeFile:
    def test_returns_text_segments_and_language(self, loaded_service):
        svc, path = loaded_service
        result = svc.transcribe_file(str(path), language="auto")
        assert result["text"] == "hello world"
        assert result["language"] == "en"
        assert len(result["segments"]) == 2
        assert result["segments"][0] == {"start_ms": 0, "end_ms": 1000, "text": "hello"}
        assert result["segments"][1] == {"start_ms": 1000, "end_ms": 2500, "text": "world"}

    def test_emits_progress_per_segment(self, loaded_service):
        svc, path = loaded_service
        progress: list[tuple[float, str]] = []
        svc.transcribe_file(str(path), on_progress=lambda p, t: progress.append((p, t)))

        assert len(progress) == 2
        # Progress fractions are end_time / total_duration, bounded to [0, 1].
        assert progress[0][0] == pytest.approx(1.0 / 2.5)
        assert progress[1][0] == pytest.approx(2.5 / 2.5)
        assert progress[0][1].strip() == "hello"
        assert progress[1][1].strip() == "world"

    def test_passes_language_through(self, loaded_service):
        svc, path = loaded_service
        svc.transcribe_file(str(path), language="es")
        assert svc._model.last_kwargs["language"] == "es"

    def test_auto_language_passes_none(self, loaded_service):
        svc, path = loaded_service
        svc.transcribe_file(str(path), language="auto")
        assert svc._model.last_kwargs["language"] is None

    def test_cancel_token_aborts_between_segments(self, loaded_service):
        """A token tripped during iteration must stop the loop and raise."""
        svc, path = loaded_service
        token = CancelToken()

        # Cancel as soon as the first segment is processed.
        def on_progress(_p, _t):
            token.cancel()

        with pytest.raises(TranscriptionCancelled):
            svc.transcribe_file(str(path), on_progress=on_progress, cancel_token=token)

    def test_no_model_raises(self, tmp_path):
        svc = TranscriptionService()  # no _model set
        f = tmp_path / "x.wav"
        f.write_bytes(b"x")
        with pytest.raises(RuntimeError):
            svc.transcribe_file(str(f))

    def test_missing_file_raises(self, loaded_service):
        svc, _ = loaded_service
        with pytest.raises(FileNotFoundError):
            svc.transcribe_file("/no/such/file.wav")
