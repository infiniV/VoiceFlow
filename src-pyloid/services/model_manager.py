"""
Model Manager service for downloading and managing Whisper models.

Provides:
- is_model_cached(): Check if model exists in cache
- get_model_info(): Get model metadata
- download_model(): Download with progress and cancellation support
- load_model(): Load already-downloaded model
- ensure_model_ready(): Download if needed + load
- get_available_models(): Get list of all supported models

Uses faster_whisper's download_model() which handles HuggingFace Hub internally.
Cache location: ~/.cache/huggingface/hub/
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import threading
import time
import os

from services.logger import get_logger

log = get_logger("model")


# All models supported by faster-whisper with approximate download sizes (bytes)
# Sizes are estimates based on the CTranslate2 converted models
MODEL_SIZES = {
    # Standard models (multilingual)
    "tiny": 75_000_000,           # ~75 MB
    "base": 145_000_000,          # ~145 MB
    "small": 466_000_000,         # ~466 MB
    "medium": 1_530_000_000,      # ~1.53 GB
    "large-v1": 3_090_000_000,    # ~3.09 GB
    "large-v2": 3_090_000_000,    # ~3.09 GB
    "large-v3": 3_090_000_000,    # ~3.09 GB
    "turbo": 1_620_000_000,       # ~1.62 GB (large-v3-turbo)
    # English-only models (slightly smaller, optimized for English)
    "tiny.en": 75_000_000,        # ~75 MB
    "base.en": 145_000_000,       # ~145 MB
    "small.en": 466_000_000,      # ~466 MB
    "medium.en": 1_530_000_000,   # ~1.53 GB
    # Distilled models (faster inference, English-only)
    "distil-small.en": 332_000_000,    # ~332 MB
    "distil-medium.en": 756_000_000,   # ~756 MB
    "distil-large-v2": 1_510_000_000,  # ~1.51 GB
    "distil-large-v3": 1_510_000_000,  # ~1.51 GB
}

# Model name to HuggingFace repo ID mapping
# Based on faster-whisper's internal mapping
MODEL_REPOS = {
    # Standard multilingual models
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "turbo": "Systran/faster-whisper-large-v3-turbo",
    # English-only models
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base.en": "Systran/faster-whisper-base.en",
    "small.en": "Systran/faster-whisper-small.en",
    "medium.en": "Systran/faster-whisper-medium.en",
    # Distilled models
    "distil-small.en": "Systran/faster-distil-whisper-small.en",
    "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
}


def _get_repo_id(model_name: str) -> str:
    """Get the HuggingFace repo ID for a model name."""
    return MODEL_REPOS.get(model_name, f"Systran/faster-whisper-{model_name}")


@dataclass
class CancelToken:
    """Token for cancelling long-running operations."""
    _cancelled: bool = False

    def cancel(self) -> None:
        """Request cancellation of the operation."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled


@dataclass
class ModelInfo:
    """Information about a Whisper model."""
    name: str
    size_bytes: int
    cached: bool


@dataclass
class DownloadProgress:
    """Progress information for model downloads."""
    model_name: str
    percent: float
    downloaded_bytes: int
    total_bytes: int
    speed_bps: float
    eta_seconds: float


class ProgressTracker:
    """
    A tqdm-compatible class that tracks download progress.

    Used as tqdm_class parameter for faster_whisper.download_model().
    """

    def __init__(
        self,
        model_name: str,
        on_progress: Callable[[DownloadProgress], None],
        cancel_token: CancelToken,
        total: int = 0,
        **kwargs
    ):
        self.model_name = model_name
        self.on_progress = on_progress
        self.cancel_token = cancel_token
        self.total = total
        self.n = 0
        self._start_time = time.time()
        self._last_update_time = self._start_time

    def update(self, n: int = 1):
        """Update progress by n bytes."""
        if self.cancel_token.is_cancelled():
            raise DownloadCancelledError("Download cancelled by user")

        self.n += n
        now = time.time()

        # Throttle updates to avoid overwhelming the UI
        if now - self._last_update_time < 0.1:  # Max 10 updates per second
            return

        self._last_update_time = now

        # Calculate progress
        elapsed = now - self._start_time
        speed = self.n / elapsed if elapsed > 0 else 0
        remaining = self.total - self.n
        eta = remaining / speed if speed > 0 else 0
        percent = (self.n / self.total * 100) if self.total > 0 else 0

        progress = DownloadProgress(
            model_name=self.model_name,
            percent=percent,
            downloaded_bytes=self.n,
            total_bytes=self.total,
            speed_bps=speed,
            eta_seconds=eta
        )

        try:
            self.on_progress(progress)
        except Exception as e:
            log.warning("Progress callback error", error=str(e))

    def close(self):
        """Close the progress tracker."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class DownloadCancelledError(Exception):
    """Raised when a download is cancelled."""
    pass


class ModelManager:
    """
    Manages Whisper model downloading and caching.

    Uses faster_whisper's download_model() which stores models in
    the huggingface cache directory (~/.cache/huggingface/hub/).
    """

    def __init__(self):
        self._download_lock = threading.Lock()

    def get_available_models(self) -> list:
        """Get list of all supported model names."""
        return list(MODEL_SIZES.keys())

    def is_model_cached(self, model_name: str) -> bool:
        """
        Check if a model is already downloaded and cached.

        Uses huggingface_hub to check if model exists in cache.

        Args:
            model_name: Name of the model (e.g., tiny, base, small, medium, large-v3, turbo)

        Returns:
            True if the model is cached, False otherwise.
        """
        try:
            from huggingface_hub import snapshot_download

            repo_id = _get_repo_id(model_name)
            # Try to get model path with local_files_only - raises if not cached
            snapshot_download(repo_id, local_files_only=True)
            return True
        except Exception:
            # Model not found in cache
            return False

    def get_model_info(self, model_name: str) -> ModelInfo:
        """
        Get information about a model.

        Args:
            model_name: Name of the model

        Returns:
            ModelInfo with name, size, and cache status
        """
        size_bytes = MODEL_SIZES.get(model_name, 0)
        cached = self.is_model_cached(model_name)

        return ModelInfo(
            name=model_name,
            size_bytes=size_bytes,
            cached=cached
        )

    def download_model(
        self,
        model_name: str,
        on_progress: Callable[[DownloadProgress], None],
        cancel_token: CancelToken
    ) -> bool:
        """
        Download a model with progress reporting and cancellation support.

        Args:
            model_name: Name of the model to download
            on_progress: Callback for progress updates
            cancel_token: Token to cancel the download

        Returns:
            True if download completed successfully, False if cancelled or failed
        """
        if cancel_token.is_cancelled():
            log.info("Download cancelled before start", model=model_name)
            return False

        with self._download_lock:
            return self._do_download(model_name, on_progress, cancel_token)

    def _do_download(
        self,
        model_name: str,
        on_progress: Callable[[DownloadProgress], None],
        cancel_token: CancelToken
    ) -> bool:
        """
        Internal download implementation.

        Uses huggingface_hub.snapshot_download() with progress tracking.
        Runs download in a daemon thread so cancellation can abandon it.

        Args:
            model_name: Name of the model to download
            on_progress: Callback for progress updates
            cancel_token: Token to cancel the download

        Returns:
            True if successful, False if cancelled or failed
        """
        from huggingface_hub import snapshot_download
        from tqdm import tqdm as tqdm_base

        log.info("Starting model download", model=model_name)

        # Get the correct repo ID for this model
        repo_id = _get_repo_id(model_name)
        log.info("Downloading from repo", repo_id=repo_id)

        # Track progress across all files
        total_size = MODEL_SIZES.get(model_name, 0)
        progress_state = {
            "files_total": 0,
            "files_done": 0,
            "bytes_downloaded": 0,
            "bytes_total": 0,  # Actual total from tqdm (more accurate than MODEL_SIZES)
            "start_time": time.time(),
            "last_update_time": time.time()
        }

        # Result holder for the download thread
        result = {"success": False, "error": None, "model_path": None}

        def send_progress():
            """Send progress update to callback."""
            now = time.time()
            # Throttle updates to max 10 per second
            if now - progress_state["last_update_time"] < 0.1:
                return
            progress_state["last_update_time"] = now

            elapsed = now - progress_state["start_time"]

            # Prefer actual byte progress over file count progress
            # Byte progress is more accurate since model.bin is most of the download
            if progress_state["bytes_total"] > 0:
                # Use actual byte progress from tqdm
                actual_bytes = progress_state["bytes_downloaded"]
                actual_total = progress_state["bytes_total"]
                percent = (actual_bytes / actual_total) * 100
            elif progress_state["files_total"] > 0:
                # Fall back to file-based progress estimation
                percent = (progress_state["files_done"] / progress_state["files_total"]) * 100
                actual_bytes = int((progress_state["files_done"] / progress_state["files_total"]) * total_size)
                actual_total = total_size
            else:
                percent = 0
                actual_bytes = 0
                actual_total = total_size

            speed = actual_bytes / elapsed if elapsed > 0 else 0
            remaining = actual_total - actual_bytes
            eta = remaining / speed if speed > 0 else 0

            try:
                on_progress(DownloadProgress(
                    model_name=model_name,
                    percent=min(percent, 99.9),  # Cap at 99.9 until truly complete
                    downloaded_bytes=actual_bytes,
                    total_bytes=actual_total,
                    speed_bps=speed,
                    eta_seconds=eta
                ))
            except Exception as e:
                log.warning("Progress callback error", error=str(e))

        # Custom tqdm class that tracks download progress
        # NOTE: huggingface_hub only uses tqdm_class for file-level progress,
        # not for individual file byte downloads (see https://github.com/huggingface/huggingface_hub/issues/1110)
        class DownloadProgressBar(tqdm_base):
            def __init__(self, *args, **kwargs):
                # Filter out any unexpected kwargs that tqdm doesn't accept
                kwargs.pop('name', None)
                super().__init__(*args, **kwargs)

            def update(self, n=1):
                # Check for cancellation - raise exception to abort download
                if cancel_token.is_cancelled():
                    raise DownloadCancelledError("Download cancelled by user")

                super().update(n)
                unit = getattr(self, 'unit', 'unknown')
                total = getattr(self, 'total', 0)
                current_n = getattr(self, 'n', 0)

                # Track file completion progress (unit='it' for iterations)
                if unit == 'it' and n > 0:
                    if progress_state["files_total"] == 0 and total > 0:
                        progress_state["files_total"] = total
                    progress_state["files_done"] = current_n
                    send_progress()

                # Track byte-based progress from individual file downloads
                if n > 0 and unit and 'B' in str(unit):
                    if total > 0 and progress_state["bytes_total"] == 0:
                        progress_state["bytes_total"] = total
                    progress_state["bytes_downloaded"] = current_n
                    send_progress()

        def download_thread():
            """Run the download in a separate thread."""
            try:
                # Send initial progress to confirm download started
                log.info("Download thread started", model=model_name, repo_id=repo_id)
                on_progress(DownloadProgress(
                    model_name=model_name,
                    percent=0.1,
                    downloaded_bytes=0,
                    total_bytes=total_size,
                    speed_bps=0,
                    eta_seconds=0
                ))

                # Use huggingface_hub directly with our custom tqdm for progress
                model_path = snapshot_download(
                    repo_id,
                    tqdm_class=DownloadProgressBar,
                )
                result["success"] = True
                result["model_path"] = model_path
            except DownloadCancelledError:
                # Expected when user cancels - not an error
                log.info("Download thread cancelled", model=model_name)
                result["error"] = "cancelled"
            except Exception as e:
                log.error("Download thread exception", error=str(e), model=model_name)
                result["error"] = str(e)

        # Start download in daemon thread
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

        # Wait for completion while checking for cancellation
        while thread.is_alive():
            if cancel_token.is_cancelled():
                log.info("Model download cancelled by user", model=model_name)
                # Thread is daemon, so it will be abandoned when we return
                return False
            thread.join(timeout=0.1)  # Check every 100ms

        # Check result
        if result["success"]:
            log.info("Model download completed", model=model_name, path=result["model_path"])

            # Send final 100% progress
            on_progress(DownloadProgress(
                model_name=model_name,
                percent=100.0,
                downloaded_bytes=total_size,
                total_bytes=total_size,
                speed_bps=0,
                eta_seconds=0
            ))
            return True
        else:
            log.error("Model download failed", model=model_name, error=result["error"])
            return False

    def load_model(self, model_name: str):
        """
        Load an already-downloaded model.

        Args:
            model_name: Name of the model to load

        Returns:
            WhisperModel instance

        Raises:
            RuntimeError: If model is not cached
        """
        if not self.is_model_cached(model_name):
            raise RuntimeError(f"Model '{model_name}' is not cached. Download it first.")

        from faster_whisper import WhisperModel

        # Use repo_id for loading to ensure correct model is loaded
        repo_id = _get_repo_id(model_name)
        log.info("Loading model", model=model_name, repo_id=repo_id)
        model = WhisperModel(
            repo_id,
            device="cpu",
            compute_type="int8"
        )
        log.info("Model loaded successfully", model=model_name)

        return model

    def ensure_model_ready(
        self,
        model_name: str,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_token: Optional[CancelToken] = None
    ):
        """
        Ensure a model is downloaded and load it.

        Downloads the model if not cached, then loads it.

        Args:
            model_name: Name of the model
            on_progress: Optional callback for download progress
            cancel_token: Optional token to cancel the download

        Returns:
            WhisperModel instance

        Raises:
            RuntimeError: If download fails or is cancelled
        """
        if not self.is_model_cached(model_name):
            log.info("Model not cached, downloading", model=model_name)

            # Set up defaults if not provided
            if on_progress is None:
                on_progress = lambda p: None
            if cancel_token is None:
                cancel_token = CancelToken()

            success = self.download_model(model_name, on_progress, cancel_token)

            if not success:
                raise RuntimeError(f"Failed to download model '{model_name}'")

        return self.load_model(model_name)


# Singleton instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get the singleton ModelManager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
