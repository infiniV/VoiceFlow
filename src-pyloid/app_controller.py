from typing import Optional, Callable, TypedDict
import threading
import time
import os
import base64
import wave
import sqlite3
from pathlib import Path
import numpy as np

from services.database import DatabaseService
from services.settings import SettingsService
from services.audio import AudioService
from services.transcription import TranscriptionService
from services.hotkey import HotkeyService
from services.clipboard import ClipboardService
from services.logger import info, error, debug, warning, exception
from services.gpu import is_cuda_available, get_gpu_name, get_cuda_compute_types, validate_device_setting, get_cudnn_status, reset_cuda_cache, has_nvidia_gpu
from services.cudnn_downloader import download_cudnn, is_cuda_libs_installed, get_download_size_mb, get_download_progress, clear_cuda_dir


class AudioAttachmentMeta(TypedDict):
    audio_relpath: str
    audio_duration_ms: int
    audio_size_bytes: int
    audio_mime: str


class AppController:
    def __init__(self):
        # Initialize services
        self.db = DatabaseService()
        self.settings_service = SettingsService(self.db)
        self.audio_service = AudioService()
        self.transcription_service = TranscriptionService()
        self.hotkey_service = HotkeyService()
        self.clipboard_service = ClipboardService()

        # Model loading state
        self._model_loaded = False
        self._model_loading = False

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

    def initialize(self):
        """Initialize the app - load model and start hotkey listener."""
        settings = self.settings_service.get_settings()

        # Set initial microphone
        mic_id = settings.microphone if settings.microphone >= 0 else None
        self.audio_service.set_device(mic_id)

        # Load whisper model in background
        def load_model():
            self._model_loading = True
            try:
                info(f"Loading model: {settings.model} on device: {settings.device}...")
                self.transcription_service.load_model(settings.model, settings.device)
                self._model_loaded = True
                info("Model loaded successfully!")
            except Exception as e:
                exception(f"Failed to load model: {e}")
                if self._on_error:
                    self._on_error(f"Failed to load model: {e}")
            finally:
                self._model_loading = False

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
        """Clean shutdown."""
        self.hotkey_service.stop()
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

        # Transcribe in background
        def transcribe():
            try:
                # Wait for model to be loaded (with timeout)
                wait_time = 0
                while not self._model_loaded and wait_time < 30:
                    if not self._model_loading:
                        warning("Model not loaded and not loading, skipping transcription")
                        if self._on_transcription_complete:
                            self._on_transcription_complete("")
                        return
                    info(f"Waiting for model to load... ({wait_time}s)")
                    time.sleep(1)
                    wait_time += 1

                if not self._model_loaded:
                    error("Model load timeout, skipping transcription")
                    if self._on_transcription_complete:
                        self._on_transcription_complete("")
                    return

                settings = self.settings_service.get_settings()
                info(f"Transcribing with language: {settings.language}")

                text = self.transcription_service.transcribe(
                    audio,
                    language=settings.language,
                )

                info(f"Transcription result: '{text}'")

                if text:
                    # Paste at cursor
                    info("Pasting text at cursor...")
                    self.clipboard_service.paste_at_cursor(text)

                    # Save to history (and audio if enabled)
                    history_id = self.db.add_history(text)

                    if settings.save_audio_to_history:
                        try:
                            audio_meta = self._save_audio_attachment(history_id, audio)
                            self.db.update_history_audio(
                                history_id,
                                audio_relpath=audio_meta["audio_relpath"],
                                audio_duration_ms=audio_meta["audio_duration_ms"],
                                audio_size_bytes=audio_meta["audio_size_bytes"],
                                audio_mime=audio_meta["audio_mime"],
                            )
                            info(f"Saved audio attachment for history {history_id}")
                        except (OSError, wave.Error, sqlite3.Error, ValueError) as exc:
                            warning(f"Failed to save audio attachment: {exc}")

                    if self._on_transcription_complete:
                        self._on_transcription_complete(text)
                else:
                    warning("No text transcribed (empty result)")
                    if self._on_transcription_complete:
                        self._on_transcription_complete("")

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
        settings = self.settings_service.get_settings()
        return {
            "language": settings.language,
            "model": settings.model,
            "device": settings.device,
            "autoStart": settings.auto_start,
            "retention": settings.retention,
            "theme": settings.theme,
            "onboardingComplete": settings.onboarding_complete,
            "microphone": settings.microphone,
            "saveAudioToHistory": settings.save_audio_to_history,
            "showPopup": settings.show_popup,
            "holdHotkey": settings.hold_hotkey,
            "holdHotkeyEnabled": settings.hold_hotkey_enabled,
            "toggleHotkey": settings.toggle_hotkey,
            "toggleHotkeyEnabled": settings.toggle_hotkey_enabled,
        }

    def update_settings(self, **kwargs) -> dict:
        debug(f"update_settings called with: {kwargs}")
        # Convert camelCase to snake_case
        mapped = {}
        if "autoStart" in kwargs:
            mapped["auto_start"] = kwargs["autoStart"]
        if "onboardingComplete" in kwargs:
            mapped["onboarding_complete"] = kwargs["onboardingComplete"]
        if "saveAudioToHistory" in kwargs:
            mapped["save_audio_to_history"] = kwargs["saveAudioToHistory"]
        if "showPopup" in kwargs:
            mapped["show_popup"] = kwargs["showPopup"]
        # Hotkey settings (camelCase to snake_case)
        if "holdHotkey" in kwargs:
            mapped["hold_hotkey"] = kwargs["holdHotkey"]
        if "holdHotkeyEnabled" in kwargs:
            mapped["hold_hotkey_enabled"] = kwargs["holdHotkeyEnabled"]
        if "toggleHotkey" in kwargs:
            mapped["toggle_hotkey"] = kwargs["toggleHotkey"]
        if "toggleHotkeyEnabled" in kwargs:
            mapped["toggle_hotkey_enabled"] = kwargs["toggleHotkeyEnabled"]

        for key in ["language", "model", "device", "retention", "theme", "microphone"]:
            if key in kwargs:
                mapped[key] = kwargs[key]

        debug(f"Mapped settings: {mapped}")
        settings = self.settings_service.update_settings(**mapped)

        # Reload model if model or device changed
        if "model" in mapped or "device" in mapped:
            def reload():
                self.transcription_service.load_model(settings.model, settings.device)
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
        wait_time = 0
        while not self._model_loaded and wait_time < 10:
            if not self._model_loading:
                return {"success": False, "error": "Model not loaded", "transcript": ""}
            debug(f"Waiting for model... ({wait_time}s)")
            time.sleep(0.5)
            wait_time += 0.5

        if not self._model_loaded:
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
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder_path])
            else:
                subprocess.Popen(['xdg-open', folder_path])
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

    def _save_audio_attachment(self, history_id: int, audio: np.ndarray) -> AudioAttachmentMeta:
        """Persist recorded audio as WAV and return metadata for DB update."""
        # Ensure audio directory exists
        audio_dir = self.db.db_path.parent / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        relpath = Path("audio") / f"history_{history_id}.wav"
        output_path = self.db.db_path.parent / relpath
        tmp_path = output_path.with_suffix(".wav.tmp")

        # Normalize audio into flat int16 PCM
        audio_array = np.asarray(audio)
        if audio_array.ndim > 1:
            audio_array = audio_array.reshape(-1)

        if np.issubdtype(audio_array.dtype, np.floating):
            audio_clipped = np.clip(audio_array, -1.0, 1.0)
            audio_int16 = (audio_clipped * 32767).astype(np.int16)
        elif audio_array.dtype == np.int16:
            audio_int16 = audio_array
        else:
            # Fallback: clip to int16 range
            audio_clipped = np.clip(audio_array, -32768, 32767)
            audio_int16 = audio_clipped.astype(np.int16)

        with wave.open(str(tmp_path), "wb") as wf:
            wf.setnchannels(self.audio_service.CHANNELS)
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(self.audio_service.SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        tmp_path.replace(output_path)

        duration_ms = int((len(audio_int16) / float(self.audio_service.SAMPLE_RATE)) * 1000)
        size_bytes = output_path.stat().st_size

        return {
            "audio_relpath": relpath.as_posix(),
            "audio_duration_ms": duration_ms,
            "audio_size_bytes": size_bytes,
            "audio_mime": "audio/wav",
        }


# Singleton instance
_controller: Optional[AppController] = None


def get_controller() -> AppController:
    global _controller
    if _controller is None:
        _controller = AppController()
    return _controller
