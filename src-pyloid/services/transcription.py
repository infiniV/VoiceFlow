import numpy as np
from typing import Optional
from faster_whisper import WhisperModel
import threading
from services.logger import get_logger
from services.model_manager import MODEL_REPOS

log = get_logger("model")


def _get_repo_id(model_name: str) -> str:
    """Get the HuggingFace repo ID for a model name."""
    return MODEL_REPOS.get(model_name, f"Systran/faster-whisper-{model_name}")


class TranscriptionService:
    def __init__(self):
        self._model: Optional[WhisperModel] = None
        self._current_model_name: str = None
        self._loading = False
        self._lock = threading.Lock()

    def load_model(self, model_name: str = "tiny"):
        """Load or switch Whisper model."""
        with self._lock:
            if self._current_model_name == model_name and self._model is not None:
                return  # Already loaded

            self._loading = True
            try:
                # Use repo_id for loading
                repo_id = _get_repo_id(model_name)
                self._model = WhisperModel(
                    repo_id,
                    device="cpu",
                    compute_type="int8",  # Faster on CPU
                )
                self._current_model_name = model_name
            finally:
                self._loading = False

    def is_loading(self) -> bool:
        return self._loading

    def get_current_model(self) -> Optional[str]:
        return self._current_model_name

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

        # Combine all segments
        segments_list = list(segments)
        log.debug("Transcription segments", segment_count=len(segments_list))
        text_parts = [segment.text for segment in segments_list]
        text = " ".join(text_parts).strip()

        return text

    def unload_model(self):
        """Unload model to free memory."""
        with self._lock:
            self._model = None
            self._current_model_name = None
