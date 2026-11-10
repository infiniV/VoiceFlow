from typing import Optional, Callable
import threading
import os
import base64

from services.database import DatabaseService
from services.settings import SettingsService, settings_to_rpc, rpc_to_settings_kwargs
from services.audio import AudioService
from services.transcription import TranscriptionService
from services.hotkey import HotkeyService
from services.clipboard import ClipboardService
from services.dictation import DictationPipeline
from services.recording.controller import MeetingsController
from services.logger import info, error, debug, warning, exception
from services.gpu import is_cuda_available, get_gpu_name, get_cuda_compute_types, validate_device_setting, get_cudnn_status, reset_cuda_cache, has_nvidia_gpu
from services.cudnn_downloader import download_cudnn, is_cuda_libs_installed, get_download_size_mb, get_download_progress, clear_cuda_dir


class AppController:
    def __init__(self):
        # Initialize services
        self.db = DatabaseService()
        self.settings_service = SettingsService(self.db)
        self.audio_service = AudioService()
        self.transcription_service = TranscriptionService()
        self.hotkey_service = HotkeyService()
        self.clipboard_service = ClipboardService()
        self.dictation = DictationPipeline(
            settings_service=self.settings_service,
            transcription_service=self.transcription_service,
            clipboard_service=self.clipboard_service,
            db=self.db,
            audio_service=self.audio_service,
            is_model_loaded=lambda: self.transcription_service.get_current_model() is not None,
            is_model_loading=self.transcription_service.is_loading,
        )

        # Meetings feature — its own self-contained controller. Constructed
        # after the shared services it depends on. See services/recording/.
        self._meetings_event_emitter: Optional[Callable[[str, dict], None]] = None
        self.meetings = MeetingsController(
            db=self.db,
            settings_service=self.settings_service,
            transcription_service=self.transcription_service,
            data_root=self.db.db_path.parent,
            event_emitter=lambda name, payload: (
                self._meetings_event_emitter(name, payload)
                if self._meetings_event_emitter is not None
                else None
            ),
        )

        # Shutdown is wired from both QApplication.aboutToQuit and the
        # post-app.run() path in main.py; this guard makes a second call a
        # no-op instead of double-stopping the hotkey listener.
        self._shutdown_done = False

        # Popup enabled state (disabled during onboarding)
        self._popup_enabled = True

        # Callbacks for UI
        self._on_recording_start: Optional[Callable[[], None]] = None
        self._on_recording_stop: Optional[Callable[[], None]] = None
        self._on_transcription_complete: Optional[Callable[[str], None]] = None
        self._on_amplitude: Optional[Callable[[float], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None

        # Setup hotkey callbacks
        self.hotkey_service.set_callbacks(
            on_activate=self._handle_hotkey_activate,
            on_deactivate=self._handle_hotkey_deactivate,
        )

        # Setup audio amplitude callback
        self.audio_service.set_amplitude_callback(self._handle_amplitude)

    def set_ui_callbacks(
        self,
        on_recording_start: Callable[[], None] = None,
        on_recording_stop: Callable[[], None] = None,
        on_transcription_complete: Callable[[str], None] = None,
        on_amplitude: Callable[[float], None] = None,
        on_error: Callable[[str], None] = None,
    ):
        self._on_recording_start = on_recording_start
        self._on_recording_stop = on_recording_stop
        self._on_transcription_complete = on_transcription_complete
        self._on_amplitude = on_amplitude
        self._on_error = on_error

    def set_meetings_event_emitter(self, emitter: Callable[[str, dict], None]) -> None:
        """Called from main.py once the popup-event signal pathway is ready.
        Routes meeting transcribe/summarize/recording-state events to the frontend."""
        self._meetings_event_emitter = emitter

    def initialize(self):
        """Initialize the app - load model and start hotkey listener."""
        settings = self.settings_service.get_settings()

        # Set initial microphone
        mic_id = settings.microphone if settings.microphone >= 0 else None
        self.audio_service.set_device(mic_id)

        # Meetings: sweep any recordings that were left in 'recording' / 'paused' state
        # from a previous unclean shutdown. Audio files survive; we just relink them
        # and queue transcription so the user doesn't silently lose hours of audio.
        try:
            recovered = self.meetings.recover_unfinished()
            if recovered:
                info(f"Recovered {len(recovered)} unfinished recording(s) from previous session")
        except Exception as exc:
            warning(f"Meetings recovery sweep failed: {exc}")

        # Load whisper model in background
        def load_model():
            """Load the configured model and report startup errors to the UI."""
            try:
                info(f"Loading model: {settings.model} on device: {settings.device}...")
                self.transcription_service.load_model(settings.model, settings.device)
                info("Model loaded successfully!")
            except Exception as e:
                exception(f"Failed to load model: {e}")
                if self._on_error:
                    self._on_error(f"Failed to load model: {e}")

        threading.Thread(target=load_model, daemon=True).start()

        # Configure hotkey service with settings
        self.hotkey_service.configure(
            hold_hotkey=settings.hold_hotkey,
            hold_enabled=settings.hold_hotkey_enabled,
            toggle_hotkey=settings.toggle_hotkey,
            toggle_enabled=settings.toggle_hotkey_enabled,
        )

        # Start hotkey listener
        self.hotkey_service.start()

        # Clean old history based on retention setting
        self.db.clear_old_history(settings.retention)

    def shutdown(self):
        """Clean shutdown. Idempotent — wired from both QApplication.aboutToQuit
        and main.py's post-app.run() path, so it can fire twice on a normal exit."""
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self.hotkey_service.stop()
        # Stop any active meeting recording before tearing down. parec /
        # sounddevice hold PipeWire / PortAudio handles that, if leaked, can
        # corrupt the global audio routing graph (observed: Teams loses
        # inbound audio after a VoiceFlow wedge + window close). Failure is
        # tolerated — recover_unfinished() on the next startup will pick up
        # any partial recording.
        try:
            if self.meetings.recorder.get_state()["state"] != "idle":
                info("Shutdown: stopping active meeting recording")
                self.meetings.stop()
        except Exception as exc:
            warning(f"Shutdown: failed to stop active meeting: {exc}")
        self.transcription_service.unload_model()

    def _handle_hotkey_activate(self):
        """Called when hotkey is pressed."""
        # Don't activate during onboarding
        if not self._popup_enabled:
            debug("Hotkey ignored - popup disabled (onboarding)")
            return

        if self._on_recording_start:
            self._on_recording_start()
        self.audio_service.start_recording()

    def _handle_hotkey_deactivate(self):
        """Called when hotkey is released."""
        if self._on_recording_stop:
            self._on_recording_stop()

        # Get recorded audio
        audio = self.audio_service.stop_recording()

        if len(audio) == 0:
            warning("No audio recorded")
            return

        info(f"Recorded {len(audio)} samples")

        # Transcribe in background. The pipeline does the work; UI callbacks
        # stay here so the pipeline remains testable without them.
        def transcribe():
            try:
                text = self.dictation.run(audio)
                if self._on_transcription_complete:
                    self._on_transcription_complete(text)
            except Exception as e:
                exception(f"Transcription error: {e}")
                if self._on_error:
                    self._on_error(f"Transcription failed: {e}")
                # Still notify completion to reset UI state
                if self._on_transcription_complete:
                    self._on_transcription_complete("")

        threading.Thread(target=transcribe, daemon=True).start()

    def _handle_amplitude(self, amplitude: float):
        """Forward amplitude to UI."""
        if self._on_amplitude:
            self._on_amplitude(amplitude)

    # Settings methods for RPC
    def get_settings(self) -> dict:
        return settings_to_rpc(self.settings_service.get_settings())

    def update_settings(self, **kwargs) -> dict:
        debug(f"update_settings called with: {kwargs}")
        mapped = rpc_to_settings_kwargs(kwargs)
        debug(f"Mapped settings: {mapped}")
        settings = self.settings_service.update_settings(**mapped)

        # Reload model if model or device changed. The thread re-reads settings
        # at execution time (not the snapshot from this call) so two rapid
        # updates converge on the latest model regardless of thread scheduling;
        # load_model itself serializes and short-circuits redundant loads.
        if "model" in mapped or "device" in mapped:
            def reload():
                """Load the latest model and device settings on the worker."""
                latest = self.settings_service.get_settings()
                self.transcription_service.load_model(latest.model, latest.device)
            threading.Thread(target=reload, daemon=True).start()

        # Update microphone if changed
        if "microphone" in mapped:
            mic_id = mapped["microphone"] if mapped["microphone"] >= 0 else None
            self.audio_service.set_device(mic_id)
            info(f"Microphone updated to: {mic_id}")

        # Reconfigure hotkey service if any hotkey settings changed
        hotkey_keys = ["hold_hotkey", "hold_hotkey_enabled", "toggle_hotkey", "toggle_hotkey_enabled"]
        if any(k in mapped for k in hotkey_keys):
            self.hotkey_service.configure(
                hold_hotkey=settings.hold_hotkey,
                hold_enabled=settings.hold_hotkey_enabled,
                toggle_hotkey=settings.toggle_hotkey,
                toggle_enabled=settings.toggle_hotkey_enabled,
            )

        return self.get_settings()

    # History methods for RPC
    def get_history(self, limit: int = 100, offset: int = 0, search: str = None, include_audio_meta: bool = False) -> list:
        return self.db.get_history(limit, offset, search, include_audio_meta)

    def delete_history(self, history_id: int):
        self.db.delete_history(history_id)

    def get_stats(self) -> dict:
        return self.db.get_stats()

    # Options for UI
    def get_options(self) -> dict:
        return {
            "models": self.settings_service.get_available_models(),
            "languages": self.settings_service.get_available_languages(),
            "retentionOptions": self.settings_service.get_retention_options(),
            "themeOptions": self.settings_service.get_theme_options(),
            "microphones": self.audio_service.get_input_devices(),
            "deviceOptions": self.settings_service.get_device_options(),
        }

    def get_gpu_info(self) -> dict:
        """Get GPU/CUDA information for the frontend."""
        cuda_available = is_cuda_available()
        cudnn_available, cudnn_message = get_cudnn_status()
        # Always try to get GPU name (to show "GPU detected but cuDNN missing")
        gpu_name = get_gpu_name()
        return {
            "cudaAvailable": cuda_available,
            "deviceCount": 1 if cuda_available else 0,
            "gpuName": gpu_name,
            "supportedComputeTypes": get_cuda_compute_types() if cuda_available else [],
            "currentDevice": self.transcription_service.get_current_device(),
            "currentComputeType": self.transcription_service.get_current_compute_type(),
            "cudnnAvailable": cudnn_available,
            "cudnnMessage": cudnn_message,
        }

    def validate_device(self, device: str) -> dict:
        """Validate a device setting before saving."""
        is_valid, error_msg = validate_device_setting(device)
        return {
            "valid": is_valid,
            "error": error_msg
        }

    def get_cudnn_download_info(self) -> dict:
        """Get info about cuDNN download status and requirements."""
        return {
            "hasNvidiaGpu": has_nvidia_gpu(),
            "cudnnInstalled": is_cuda_libs_installed(),
            "downloadSizeMb": get_download_size_mb(),
        }

    def download_cudnn(self, progress_callback=None) -> dict:
        """Download and install cuDNN and cuBLAS libraries."""
        info("Starting CUDA libraries download")
        success, error_msg = download_cudnn(progress_callback=progress_callback)
        if success:
            # Reset cache so next check picks up the new DLLs
            reset_cuda_cache()
            info("CUDA libraries download complete")
        else:
            error("CUDA libraries download failed", error=error_msg)
        return {
            "success": success,
            "error": error_msg,
        }

    def get_cudnn_download_progress(self) -> dict:
        """Get current CUDA libraries download progress."""
        return get_download_progress()

    def clear_cuda_libs(self) -> dict:
        """Clear downloaded CUDA libraries (cuDNN + cuBLAS)."""
        info("Clearing CUDA libraries")
        success = clear_cuda_dir()
        if success:
            reset_cuda_cache()
            info("CUDA libraries cleared")
        return {"success": success}

    def stop_recording(self):
        """Manually stop recording (called from stop button)."""
        debug("Manual stop_recording called")
        self.hotkey_service.force_deactivate()

    def manual_toggle_recording(self) -> dict:
        """Toggle recording from a UI button - mirrors hotkey behaviour.

        Returns {"recording": bool} reflecting the new state.
        """
        if self.hotkey_service.is_recording():
            stopped = self.hotkey_service.manual_stop()
            return {"recording": False, "changed": stopped}
        if not self._popup_enabled:
            warning("Manual recording ignored - popup disabled (onboarding)")
            return {"recording": False, "changed": False, "error": "onboarding_active"}
        started = self.hotkey_service.manual_start()
        return {"recording": started, "changed": started}

    def get_recording_state(self) -> dict:
        """Return the current recording state for the UI."""
        return {
            "recording": self.hotkey_service.is_recording(),
            "mode": self.hotkey_service.get_active_mode(),
        }

    def start_test_recording(self):
        """Start recording for onboarding test (no hotkey needed)."""
        debug("Starting test recording")
        self.audio_service.start_recording()

    def stop_test_recording(self) -> dict:
        """Stop test recording, transcribe, and return result (no paste/history)."""
        debug("Stopping test recording")
        audio = self.audio_service.stop_recording()

        if len(audio) == 0:
            warning("No audio recorded in test")
            return {"success": False, "error": "No audio recorded", "transcript": ""}

        info(f"Test recorded {len(audio)} samples")

        # Wait for model if needed
        readiness = self.dictation.wait_for_model(timeout_s=10, poll_s=0.5)
        if readiness == "absent":
            return {"success": False, "error": "Model not loaded", "transcript": ""}
        if readiness == "timeout":
            return {"success": False, "error": "Model loading timeout", "transcript": ""}

        try:
            settings = self.settings_service.get_settings()
            text = self.transcription_service.transcribe(
                audio,
                language=settings.language,
            )
            info(f"Test transcription: '{text}'")
            return {"success": True, "transcript": text or ""}
        except Exception as e:
            exception(f"Test transcription error: {e}")
            return {"success": False, "error": str(e), "transcript": ""}

    def open_data_folder(self):
        """Open the folder containing application data."""
        try:
            folder_path = str(self.db.db_path.parent)
            info(f"Opening data folder: {folder_path}")
            import subprocess, sys
            from services.process_env import system_env
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder_path])
            else:
                subprocess.Popen(['xdg-open', folder_path], env=system_env(),
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except Exception as e:
            error(f"Failed to open data folder: {e}")

    def set_popup_enabled(self, enabled: bool):
        """Enable or disable the popup/hotkey functionality."""
        self._popup_enabled = enabled
        debug(f"Popup {'enabled' if enabled else 'disabled'}")

    def reset_all_data(self):
        """Reset all data and return to fresh state."""
        info("Resetting all user data...")
        self.db.reset_all_data()
        # Reset settings service cache
        self.settings_service._cache = None
        info("All data has been reset")

    def get_history_audio(self, history_id: int) -> dict:
        """Fetch audio attachment for a history entry as base64."""
        entry = self.db.get_history_entry(history_id)
        if not entry or not entry.get("audio_relpath"):
            raise FileNotFoundError("No audio stored for this history item")

        data_dir = self.db.db_path.parent
        audio_root = (data_dir / "audio").resolve()
        audio_path = (data_dir / entry["audio_relpath"]).resolve()

        try:
            audio_path.relative_to(audio_root)
        except ValueError:
            raise FileNotFoundError("Audio path is invalid")

        if not audio_path.exists():
            raise FileNotFoundError("Audio file missing on disk")

        data = audio_path.read_bytes()
        return {
            "base64": base64.b64encode(data).decode("utf-8"),
            "mime": entry.get("audio_mime") or "audio/wav",
            "fileName": audio_path.name,
            "sizeBytes": audio_path.stat().st_size,
            "durationMs": entry.get("audio_duration_ms"),
        }


# Singleton instance
_controller: Optional[AppController] = None


def get_controller() -> AppController:
    global _controller
    if _controller is None:
        _controller = AppController()
    return _controller
