"""Tests for slice 6 — crash-recovery sweep on startup (Q5).

If Dictore exits uncleanly mid-recording the WAV file is on disk but the DB
row is left in `recorder_state ∈ {recording, paused}`. On the next launch we
sweep those rows, fix the WAV header via soundfile, mark them stopped, and
enqueue transcription so the user doesn't silently lose hours of audio.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from services.database import DatabaseService
from services.recording.recovery import recover_unfinished_recordings


@pytest.fixture
def db_and_root():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        db = DatabaseService(root / "test.db")
        (root / "recordings").mkdir()
        yield db, root


def _make_wav(path: Path, seconds: float, sample_rate: int = 16000, channels: int = 1) -> None:
    n = int(seconds * sample_rate)
    data = np.zeros((n, channels), dtype=np.float32)
    sf.write(str(path), data, sample_rate, subtype="PCM_16")


class TestRecoverySweep:
    def test_no_unfinished_recordings_is_a_no_op(self, db_and_root):
        db, root = db_and_root
        enqueued: list[int] = []
        result = recover_unfinished_recordings(db, root, on_recovered=enqueued.append)
        assert result == []
        assert enqueued == []

    def test_recovers_a_recording_with_valid_wav(self, db_and_root):
        db, root = db_and_root
        rid = db.create_recording(title="Crashed", sources=["mic"])
        db.set_recording_recorder_state(rid, "recording")
        wav_rel = f"recordings/{rid}_crashed.wav"
        _make_wav(root / wav_rel, seconds=3.5)
        db.set_recording_audio(
            rid, audio_relpath=wav_rel, duration_ms=None, size_bytes=None,
            sample_rate=None, channels=None,
        )

        enqueued: list[int] = []
        recovered_ids = recover_unfinished_recordings(db, root, on_recovered=enqueued.append)

        assert recovered_ids == [rid]
        assert enqueued == [rid]
        rec = db.get_recording(rid)
        assert rec["recorder_state"] is None
        assert rec["audio_duration_ms"] == 3500
        assert rec["audio_sample_rate"] == 16000
        assert rec["audio_channels"] == 1
        assert rec["audio_size_bytes"] > 0
        assert rec["transcript_status"] == "pending"

    def test_recovers_paused_recordings_too(self, db_and_root):
        db, root = db_and_root
        rid = db.create_recording(title="Paused crash", sources=["mic"])
        db.set_recording_recorder_state(rid, "paused")
        wav_rel = f"recordings/{rid}.wav"
        _make_wav(root / wav_rel, seconds=1.0)
        db.set_recording_audio(rid, wav_rel, None, None, None, None)

        recover_unfinished_recordings(db, root, on_recovered=lambda _: None)
        assert db.get_recording(rid)["recorder_state"] is None

    def test_recovers_stereo_recording(self, db_and_root):
        db, root = db_and_root
        rid = db.create_recording(title="Stereo", sources=["mic", "loopback"])
        db.set_recording_recorder_state(rid, "recording")
        wav_rel = f"recordings/{rid}.wav"
        _make_wav(root / wav_rel, seconds=2.0, channels=2)
        db.set_recording_audio(rid, wav_rel, None, None, None, None)

        recover_unfinished_recordings(db, root, on_recovered=lambda _: None)
        rec = db.get_recording(rid)
        assert rec["audio_channels"] == 2
        assert rec["audio_duration_ms"] == 2000

    def test_missing_wav_marks_recording_errored(self, db_and_root):
        """If the WAV is gone we still need to clear recorder_state — leaving the
        row stuck in 'recording' forever would block all future recordings."""
        db, root = db_and_root
        rid = db.create_recording(title="Gone", sources=["mic"])
        db.set_recording_recorder_state(rid, "recording")
        db.set_recording_audio(rid, "recordings/missing.wav", None, None, None, None)

        enqueued: list[int] = []
        result = recover_unfinished_recordings(db, root, on_recovered=enqueued.append)

        assert result == []  # not recovered for transcription
        assert enqueued == []
        rec = db.get_recording(rid)
        assert rec["recorder_state"] is None
        assert rec["transcript_status"] == "error"
        assert "missing" in (rec["transcript_error"] or "").lower()

    def test_recording_without_audio_path_marked_errored(self, db_and_root):
        """A row left in recording state with no audio_relpath is a true crash before
        the file ever got created — mark errored, no recovery possible."""
        db, root = db_and_root
        rid = db.create_recording(title="Pre-file crash", sources=["mic"])
        db.set_recording_recorder_state(rid, "recording")  # no set_recording_audio call

        enqueued: list[int] = []
        recover_unfinished_recordings(db, root, on_recovered=enqueued.append)

        assert enqueued == []
        rec = db.get_recording(rid)
        assert rec["recorder_state"] is None
        assert rec["transcript_status"] == "error"

    def test_already_completed_recordings_untouched(self, db_and_root):
        """recorder_state IS NULL → don't touch."""
        db, root = db_and_root
        rid = db.create_recording(title="OK", sources=["mic"])
        wav_rel = f"recordings/{rid}.wav"
        _make_wav(root / wav_rel, seconds=1.0)
        db.set_recording_audio(rid, wav_rel, 1000, 32044, 16000, 1)
        # recorder_state stays None

        result = recover_unfinished_recordings(db, root, on_recovered=lambda _: None)
        assert result == []
