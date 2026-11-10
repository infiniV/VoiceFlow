"""
Model Manager service for downloading and managing Whisper models.

Provides:
- is_model_cached(): Check if model exists in cache
- get_model_info(): Get model metadata
- download_model(): Download with progress and cancellation support
- start_download() / cancel_download() / get_download_status(): single-flight
  background download session with event emission (the RPC surface)
- get_available_models(): Get list of all supported models
- delete_model() / clear_cache(): Cache management

Model loading lives in TranscriptionService (the only load path — it resolves
the user's device preference). The model catalog (names, sizes, repos) lives
in services.model_catalog.

Cache location: ~/.cache/huggingface/hub/
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import threading
import time
import os
import io

from services.logger import get_logger
from services.model_catalog import (
    MODEL_SIZES,
    MODEL_REPOS,
    get_repo_id as _get_repo_id,
    hf_cache_folder_name,
)

log = get_logger("model")

_REQUIRED_MODEL_FILES = ("config.json", "model.bin", "tokenizer.json")
_DOWNLOAD_BUSY = "A model download is still running. Cancel it and wait for it to stop before deleting cached files."


def _has_model_files(snapshot: str) -> bool:
    """Check that the files needed for offline loading are present and nonempty."""
    path = Path(snapshot)
    return all((path / name).is_file() and (path / name).stat().st_size > 0
               for name in _REQUIRED_MODEL_FILES)


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
    repo_id: str = ""


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
        # Single-flight download session state. Guarded by _session_lock;
        # only one background download runs at a time and its progress is
        # queryable so the UI can re-attach after navigating away.
        self._session_lock = threading.Lock()
        self._session: Optional[dict] = None

    def get_available_models(self) -> list:
        """Get list of all supported model names."""
        return list(MODEL_SIZES.keys())

    def get_cache_dir(self) -> str:
        """Return the resolved HuggingFace hub cache directory path."""
        try:
            from huggingface_hub.constants import HF_HUB_CACHE
            return str(Path(HF_HUB_CACHE).resolve())
        except Exception:
            return str((Path.home() / ".cache" / "huggingface" / "hub").resolve())

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
            self.get_cached_model_path(model_name)
            return True
        except Exception:
            # Model not found in cache
            return False

    def get_cached_model_path(self, model_name: str) -> str:
        """Resolve a complete local snapshot without initiating a download."""
        from huggingface_hub import snapshot_download

        snapshot = snapshot_download(_get_repo_id(model_name), local_files_only=True)
        if not _has_model_files(snapshot):
            raise FileNotFoundError(f"The cached {model_name} model is incomplete. Retry the download.")
        return snapshot

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
            cached=cached,
            repo_id=_get_repo_id(model_name)
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

        Returns True on success and False on cancellation. Download errors
        propagate so the UI can show the reason.
        """
        with self._download_lock:
            if cancel_token.is_cancelled():
                return False
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
        Holds the cache lock until the Hub has closed its files.

        Args:
            model_name: Name of the model to download
            on_progress: Callback for progress updates
            cancel_token: Token to cancel the download

        Returns:
            True if successful, False if cancelled. Download failures propagate.
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
                # bytes_downloaded counts every chunk including small metadata
                # files that aren't always reflected in bytes_total. Cap to
                # avoid >100% drift before the file-count bar catches up.
                if actual_bytes > actual_total:
                    actual_bytes = actual_total
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

        # Custom tqdm class that tracks download progress.
        #
        # huggingface_hub uses tqdm_class for two bars: a shared bytes_progress
        # bar (unit="B") that aggregates per-file chunk updates, and a
        # thread_map outer bar (unit="it") for file-count progress.
        #
        # IMPORTANT: tqdm with disable=None auto-disables when stderr isn't a
        # TTY (which is the case in packaged GUI builds). When disabled, tqdm
        # silently drops self.n increments and self.unit, so our previous
        # implementation never reported byte progress for big-file downloads.
        # That made multi-GB models look frozen at single-digit % until the
        # first/last file boundary, which users perceive as "won't download".
        # Fix: track bytes ourselves via _vf_n and remember the unit kwarg
        # before super().__init__ can clobber it. Force disable=False so
        # tqdm doesn't no-op our updates either.
        class DownloadProgressBar(tqdm_base):
            def __init__(self, *args, **kwargs):
                kwargs.pop('name', None)
                # Stash unit before super init - tqdm with disable=True drops it
                self._vf_unit = kwargs.get('unit', 'it')
                # Force enabled so super().update() actually runs
                kwargs['disable'] = False
                # Redirect tqdm console writes to dummy buffer; sys.stderr can
                # be None in pyinstaller --windowed builds.
                kwargs['file'] = io.StringIO()
                super().__init__(*args, **kwargs)
                self._vf_n = 0

            def update(self, n=1):
                # Check for cancellation - raise exception to abort download
                if cancel_token.is_cancelled():
                    raise DownloadCancelledError("Download cancelled by user")

                super().update(n)
                if n <= 0:
                    return

                self._vf_n += n
                # self.total is read live - hf_hub keeps incrementing the
                # bytes bar's total as new files are queued.
                total = getattr(self, 'total', 0) or 0

                if 'B' in self._vf_unit:
                    # Byte-level progress (the meaningful one for big models)
                    progress_state["bytes_total"] = total
                    progress_state["bytes_downloaded"] = self._vf_n
                    send_progress()
                else:
                    # File-count progress (fallback when bytes bar is silent)
                    if progress_state["files_total"] == 0 and total > 0:
                        progress_state["files_total"] = total
                    progress_state["files_done"] = self._vf_n
                    send_progress()

        on_progress(DownloadProgress(model_name, 0, 0, total_size, 0, 0))
        if cancel_token.is_cancelled():
            return False
        try:
            model_path = snapshot_download(repo_id, tqdm_class=DownloadProgressBar)
        except DownloadCancelledError:
            return False

        if cancel_token.is_cancelled():
            return False
        if not _has_model_files(model_path):
            raise RuntimeError("The model download is incomplete. Retry to finish downloading it.")

        log.info("Model download completed", model=model_name, path=model_path)
        on_progress(DownloadProgress(model_name, 100, total_size, total_size, 0, 0))
        return True

    # ------------------------------------------------------------------
    # Background download session (the RPC-facing surface)
    #
    # One download at a time. Starting a new download cancels the previous
    # one. Progress and completion are pushed through the emit callback as
    # ("download-progress", payload) / ("download-complete", payload) and the
    # latest progress snapshot is queryable via get_download_status() so a
    # remounted UI can re-attach to an in-flight download.
    # ------------------------------------------------------------------

    def start_download(self, model_name: str, emit: Callable[[str, dict], None]) -> dict:
        """Start a background download session for a model.

        Args:
            model_name: Name of the model to download
            emit: Callback(event_name, payload) used for progress/completion
                  events. Payload keys are camelCase (the frontend contract).

        Returns:
            dict: {"success": True, "alreadyCached": True} if nothing to do,
                  {"success": True, "started": True} if a session started.
        """
        with self._session_lock:
            current = self._session
            if current is not None and not current["done"]:
                if current["model"] == model_name and not current["token"].is_cancelled():
                    return {"success": True, "started": True}
                log.info("Cancelling previous download for new request")
                current["token"].cancel()

            if self.is_model_cached(model_name):
                log.info("Model already cached", model=model_name)
                emit("download-complete", {
                    "model": model_name,
                    "success": True,
                    "alreadyCached": True
                })
                return {"success": True, "alreadyCached": True}

            token = CancelToken()
            session = {
                "model": model_name,
                "token": token,
                "done": False,
                "progress": None,  # last DownloadProgress payload (camelCase)
            }

            def on_progress(progress: DownloadProgress):
                """Publish progress only while this session is current."""
                payload = {
                    "model": progress.model_name,
                    "percent": progress.percent,
                    "downloadedBytes": progress.downloaded_bytes,
                    "totalBytes": progress.total_bytes,
                    "speedBps": progress.speed_bps,
                    "etaSeconds": progress.eta_seconds
                }
                with self._session_lock:
                    if self._session is session and not token.is_cancelled():
                        session["progress"] = payload
                        emit("download-progress", payload)

            def run():
                """Publish the outcome once the transfer has released the cache."""
                payload = {"model": model_name, "success": False}
                try:
                    payload["success"] = self.download_model(model_name, on_progress, token)
                except Exception as e:
                    log.error("Model download failed", model=model_name, error=str(e))
                    payload["error"] = str(e)
                with self._session_lock:
                    session["done"] = True
                    payload["cancelled"] = token.is_cancelled() and not payload["success"]
                    if self._session is session:
                        emit("download-complete", payload)

            session["thread"] = threading.Thread(target=run, daemon=True)
            self._session = session
            session["thread"].start()

        log.info("Started model download", model=model_name)
        return {"success": True, "started": True}

    def cancel_download(self) -> dict:
        """Cancel the active download session, if any."""
        with self._session_lock:
            session = self._session
            if session is not None and not session["done"] and not session["token"].is_cancelled():
                log.info("Cancelling model download", model=session["model"])
                session["token"].cancel()
                return {"success": True, "cancelled": True}
        return {"success": True, "cancelled": False}

    def get_download_status(self) -> dict:
        """Snapshot of the active download session (camelCase payload).

        Returns {"active": False} when no download is running; otherwise the
        last progress payload plus "active": True so the UI can re-attach.
        """
        with self._session_lock:
            session = self._session
            if session is None or session["done"]:
                return {"active": False, "model": None}
            progress = session["progress"] or {
                "model": session["model"],
                "percent": 0,
                "downloadedBytes": 0,
                "totalBytes": MODEL_SIZES.get(session["model"], 0),
                "speedBps": 0,
                "etaSeconds": 0,
            }
            return {"active": True, "cancelling": session["token"].is_cancelled(), **progress}

    def clear_cache(self) -> dict:
        """
        Clear all cached Whisper models from the HuggingFace cache directory.

        Returns:
            dict with:
                - success: bool indicating if operation succeeded
                - deleted_bytes: total bytes deleted
                - deleted_models: list of model names that were deleted
                - error: error message if failed
        """
        import shutil

        log.info("Clearing model cache")

        deleted_bytes = 0
        deleted_models = []

        if not self._download_lock.acquire(blocking=False):
            return {"success": False, "deleted_bytes": 0, "deleted_models": [], "error": _DOWNLOAD_BUSY}
        try:
            cache_dir = Path(self.get_cache_dir())

            if not cache_dir.exists():
                log.info("Cache directory does not exist, nothing to clear")
                return {
                    "success": True,
                    "deleted_bytes": 0,
                    "deleted_models": [],
                    "error": None
                }

            # Find and delete all faster-whisper model directories
            # HuggingFace stores models as: models--{org}--{repo}
            for model_name, repo_id in MODEL_REPOS.items():
                model_cache_path = cache_dir / hf_cache_folder_name(repo_id)

                if model_cache_path.exists():
                    # Calculate size before deleting
                    size = sum(f.stat().st_size for f in model_cache_path.rglob("*") if f.is_file())
                    log.info("Deleting model cache", model=model_name, path=str(model_cache_path), size_bytes=size)
                    shutil.rmtree(model_cache_path)
                    deleted_bytes += size
                    deleted_models.append(model_name)

            log.info("Model cache cleared",
                     deleted_count=len(deleted_models),
                     deleted_bytes=deleted_bytes)

            return {
                "success": True,
                "deleted_bytes": deleted_bytes,
                "deleted_models": deleted_models,
                "error": None
            }

        except Exception as e:
            log.error("Failed to clear model cache", error=str(e))
            return {
                "success": False,
                "deleted_bytes": deleted_bytes,
                "deleted_models": deleted_models,
                "error": str(e)
            }
        finally:
            self._download_lock.release()

    def delete_model(self, model_name: str) -> dict:
        """
        Delete a single cached Whisper model from the HuggingFace cache directory.

        Returns:
            dict with:
                - success: bool indicating if operation succeeded
                - deleted_bytes: total bytes freed
                - deleted_model: name of the model deleted, or None
                - error: error message if failed
        """
        import shutil

        repo_id = MODEL_REPOS.get(model_name)
        if repo_id is None:
            log.error("Refusing to delete unknown model", model=model_name)
            return {
                "success": False,
                "deleted_bytes": 0,
                "deleted_model": None,
                "error": "unknown model",
            }

        log.info("Deleting model", model=model_name)

        if not self._download_lock.acquire(blocking=False):
            return {"success": False, "deleted_bytes": 0, "deleted_model": None, "error": _DOWNLOAD_BUSY}
        try:
            cache_dir = Path(self.get_cache_dir())
            model_cache_path = cache_dir / hf_cache_folder_name(repo_id)

            if not model_cache_path.exists():
                log.info("Model not cached, nothing to delete", model=model_name)
                return {
                    "success": True,
                    "deleted_bytes": 0,
                    "deleted_model": None,
                    "error": None,
                }

            size = sum(f.stat().st_size for f in model_cache_path.rglob("*") if f.is_file())
            log.info("Deleting model cache", model=model_name, path=str(model_cache_path), size_bytes=size)
            shutil.rmtree(model_cache_path)

            return {
                "success": True,
                "deleted_bytes": size,
                "deleted_model": model_name,
                "error": None,
            }

        except Exception as e:
            log.error("Failed to delete model", model=model_name, error=str(e))
            return {
                "success": False,
                "deleted_bytes": 0,
                "deleted_model": None,
                "error": str(e),
            }
        finally:
            self._download_lock.release()


# Singleton instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get the singleton ModelManager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
