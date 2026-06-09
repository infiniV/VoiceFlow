"""Crash-recovery sweep for unfinished recordings (Q5).

On Dictore startup we look for any `recordings` row with a non-NULL
`recorder_state` — that's a recording that was running when the app died.
For each, we:

  * Open the WAV file via soundfile to read its actual duration / channels /
    sample rate (soundfile is forgiving — it can read even when the RIFF size
    field was never finalised by a clean close).
  * Update the DB row with that metadata, clear `recorder_state`, and leave
    `transcript_status='pending'` so the transcribe job queue picks it up.
  * If the file is missing or unreadable, mark the row `transcript_status='error'`
    and clear `recorder_state` — leaving it stuck would block all future starts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import soundfile as sf

from services.database import DatabaseService
from services.logger import get_logger

log = get_logger("recording")

OnRecovered = Callable[[int], None]


def recover_unfinished_recordings(
    db: DatabaseService,
    data_root: Path,
    on_recovered: Optional[OnRecovered] = None,
) -> list[int]:
    """Sweep the DB for unfinished recordings. Returns the IDs that were
    successfully recovered (file readable, audio metadata refreshed). The
    `on_recovered` callback is invoked for each — used by AppController to
    enqueue background transcription."""
    recovered: list[int] = []
    rows = db.list_unfinished_recordings()
    if not rows:
        return recovered

    for row in rows:
        rid = row["id"]
        relpath = row.get("audio_relpath")

        if not relpath:
            db.update_transcript_status(
                rid, status="error", error="recorder crashed before audio file was created"
            )
            db.set_recording_recorder_state(rid, None)
            log.warning("recovery: no audio file recorded", recording_id=rid)
            continue

        wav_path = (data_root / relpath).resolve()
        try:
            wav_path.relative_to(data_root.resolve())
        except ValueError:
            db.update_transcript_status(rid, status="error", error="audio path outside data root")
            db.set_recording_recorder_state(rid, None)
            log.warning("recovery: refused path traversal", recording_id=rid, path=str(wav_path))
            continue

        if not wav_path.exists():
            db.update_transcript_status(
                rid, status="error", error=f"audio file missing on disk: {relpath}"
            )
            db.set_recording_recorder_state(rid, None)
            log.warning("recovery: audio missing", recording_id=rid, path=str(wav_path))
            continue

        try:
            with sf.SoundFile(str(wav_path)) as snd:
                frames = snd.frames
                sample_rate = snd.samplerate
                channels = snd.channels
            duration_ms = int(frames * 1000 / sample_rate) if sample_rate else 0
            size_bytes = wav_path.stat().st_size
        except Exception as exc:
            db.update_transcript_status(rid, status="error", error=f"audio unreadable: {exc}")
            db.set_recording_recorder_state(rid, None)
            log.warning("recovery: audio unreadable", recording_id=rid, error=str(exc))
            continue

        db.set_recording_audio(
            rid,
            audio_relpath=relpath,
            duration_ms=duration_ms,
            size_bytes=size_bytes,
            sample_rate=sample_rate,
            channels=channels,
        )
        db.update_transcript_status(rid, status="pending", progress=0)
        db.set_recording_recorder_state(rid, None)
        log.info(
            "recovery: recording recovered",
            recording_id=rid, duration_ms=duration_ms, channels=channels,
        )
        recovered.append(rid)
        if on_recovered is not None:
            try:
                on_recovered(rid)
            except Exception as exc:
                log.error("recovery: on_recovered callback failed",
                          recording_id=rid, error=str(exc))

    return recovered
