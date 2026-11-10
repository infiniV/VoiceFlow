import os
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from faster_whisper import WhisperModel

from services.logger import get_logger
from services.model_manager import get_model_manager
from services.gpu import resolve_device, get_compute_type

log = get_logger("model")


class CancelToken:
    """Cooperative cancellation flag. Background jobs check `is_cancelled` at
    safe points; callers flip it via `cancel()`."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()


class TranscriptionCancelled(Exception):
    """Raised by long-running transcription when the cancel token is tripped."""


class TranscriptionService:
    def __init__(self):
        self._model: Optional[WhisperModel] = None
        self._current_model_name: str = None
        self._current_device: str = None
        self._current_compute_type: str = None
        self._loading = False
        self._lock = threading.Lock()

    def load_model(self, model_name: str = "tiny", device_preference: str = "auto"):
        """Load or switch Whisper model.

        Args:
            model_name: Name of the Whisper model
            device_preference: "auto", "cpu", or "cuda"
        """
        # Resolve device and compute type
        device = resolve_device(device_preference)
        compute_type = get_compute_type(device)

        with self._lock:
            # Check if we need to reload
            if (self._current_model_name == model_name
                and self._current_device == device
                and self._model is not None):
                return  # Already loaded with same config

            model_path = get_model_manager().get_cached_model_path(model_name)
            self._loading = True
            try:
                log.info(
                    "Loading model",
                    model=model_name,
                    device=device,
                    compute_type=compute_type
                )
                self._model = WhisperModel(
                    model_path,
                    device=device,
                    compute_type=compute_type,
                    local_files_only=True,
                )
                self._current_model_name = model_name
                self._current_device = device
                self._current_compute_type = compute_type
                log.info("Model loaded successfully", device=device, compute_type=compute_type)
            except Exception as e:
                log.error("Failed to load model", error=str(e), device=device)
                # If CUDA failed, try falling back to CPU
                if device == "cuda":
                    log.warning("CUDA load failed, falling back to CPU")
                    self._model = WhisperModel(
                        model_path,
                        device="cpu",
                        compute_type="int8",
                        local_files_only=True,
                    )
                    self._current_model_name = model_name
                    self._current_device = "cpu"
                    self._current_compute_type = "int8"
                    log.info("Model loaded on CPU fallback")
                else:
                    raise
            finally:
                self._loading = False

    def is_loading(self) -> bool:
        return self._loading

    def get_current_model(self) -> Optional[str]:
        return self._current_model_name

    def get_current_device(self) -> str:
        """Get the device currently being used."""
        return self._current_device or "cpu"

    def get_current_compute_type(self) -> str:
        """Get the compute type currently being used."""
        return self._current_compute_type or "int8"

    def transcribe(
        self,
        audio: np.ndarray,
        language: str = "auto",
    ) -> str:
        """Transcribe audio to text."""
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if len(audio) == 0:
            return ""

        # Ensure audio is float32 and normalized
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Normalize if needed
        max_val = np.abs(audio).max()
        if max_val > 1.0:
            audio = audio / max_val

        # Transcribe
        language_arg = None if language == "auto" else language

        log.debug("Audio stats", length=len(audio), max_amplitude=float(np.abs(audio).max()), mean_amplitude=float(np.abs(audio).mean()))

        try:
            segments, info = self._model.transcribe(
                audio,
                language=language_arg,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,  # Less aggressive silence detection
                    speech_pad_ms=400,  # More padding around speech
                ),
            )
        except RuntimeError as e:
            if "not found or cannot be loaded" in str(e) and self._current_device == "cuda":
                log.warning("CUDA runtime error during transcription, reloading on CPU", error=str(e))
                model_name = self._current_model_name
                model_path = get_model_manager().get_cached_model_path(model_name)
                self._model = WhisperModel(model_path, device="cpu", compute_type="int8", local_files_only=True)
                self._current_device = "cpu"
                self._current_compute_type = "int8"
                log.info("Model reloaded on CPU fallback")
                segments, info = self._model.transcribe(
                    audio,
                    language=language_arg,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=500,
                        speech_pad_ms=400,
                    ),
                )
            else:
                raise

        # Combine all segments
        segments_list = list(segments)
        log.debug("Transcription segments", segment_count=len(segments_list))
        text_parts = [segment.text for segment in segments_list]
        text = " ".join(text_parts).strip()

        return text

    def transcribe_file(
        self,
        audio_path: str,
        language: str = "auto",
        on_progress: Optional[Callable[[float, str], None]] = None,
        cancel_token: Optional[CancelToken] = None,
    ) -> dict:
        """Transcribe a WAV file. Yields segment-level progress.

        Returns: ``{"text": str, "segments": [{"start_ms", "end_ms", "text"}], "language": str}``

        Raises:
          RuntimeError if no model is loaded.
          FileNotFoundError if the audio path doesn't exist.
          TranscriptionCancelled if `cancel_token` is tripped between segments.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(audio_path)

        language_arg = None if language == "auto" else language

        log.info(
            "transcribing file",
            path=str(audio_path),
            language=language_arg,
        )

        try:
            segments, info = self._model.transcribe(
                audio_path,
                language=language_arg,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=400,
                ),
            )
        except Exception:
            log.exception("transcribe_file: model error", path=str(audio_path))
            raise

        total = float(getattr(info, "duration", 0.0)) or 0.0
        detected_language = getattr(info, "language", None)

        out_segments: list[dict] = []
        text_parts: list[str] = []

        try:
            for seg in segments:
                if cancel_token is not None and cancel_token.is_cancelled:
                    raise TranscriptionCancelled()
                start_ms = int(float(seg.start) * 1000)
                end_ms = int(float(seg.end) * 1000)
                text = (seg.text or "").strip()
                out_segments.append({"start_ms": start_ms, "end_ms": end_ms, "text": text})
                if text:
                    text_parts.append(text)
                if on_progress is not None:
                    fraction = (float(seg.end) / total) if total > 0 else 0.0
                    if fraction < 0.0:
                        fraction = 0.0
                    elif fraction > 1.0:
                        fraction = 1.0
                    try:
                        on_progress(fraction, text)
                    except Exception:
                        log.exception("transcribe_file: progress callback raised")
        finally:
            # Discard the generator explicitly so faster-whisper releases its
            # internal decode buffers even on cancellation.
            del segments

        full_text = " ".join(text_parts).strip()
        return {
            "text": full_text,
            "segments": out_segments,
            "language": detected_language,
        }

    def unload_model(self):
        """Unload model to free memory."""
        with self._lock:
            self._model = None
            self._current_model_name = None
            self._current_device = None
            self._current_compute_type = None
