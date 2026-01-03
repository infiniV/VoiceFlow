from typing import Optional
from pyloid.rpc import PyloidRPC, RPCContext
from app_controller import get_controller
from services.logger import get_logger
from services.model_manager import get_model_manager, CancelToken, DownloadProgress
import threading

log = get_logger("window")
model_log = get_logger("model")

server = PyloidRPC()

# Callbacks that main.py will register
_on_onboarding_complete = None
_on_data_reset = None
_send_download_progress = None  # Callback to send progress to frontend

# Active download state
_active_download_token: CancelToken = None
_download_thread: threading.Thread = None


def register_download_progress_callback(callback):
    """Register callback to send download progress to frontend."""
    global _send_download_progress
    _send_download_progress = callback


def register_onboarding_complete_callback(callback):
    """Register callback to be called when onboarding completes."""
    global _on_onboarding_complete
    _on_onboarding_complete = callback


def register_data_reset_callback(callback):
    """Register callback to be called when data is reset."""
    global _on_data_reset
    _on_data_reset = callback


@server.method()
async def get_settings():
    controller = get_controller()
    return controller.get_settings()


@server.method()
async def update_settings(
    *,
    language: Optional[str] = None,
    model: Optional[str] = None,
    device: Optional[str] = None,
    autoStart: Optional[bool] = None,
    retention: Optional[int] = None,
    theme: Optional[str] = None,
    onboardingComplete: Optional[bool] = None,
    microphone: Optional[int] = None,
    saveAudioToHistory: Optional[bool] = None,
    holdHotkey: Optional[str] = None,
    holdHotkeyEnabled: Optional[bool] = None,
    toggleHotkey: Optional[str] = None,
    toggleHotkeyEnabled: Optional[bool] = None,
):
    controller = get_controller()
    kwargs = {}
    if language is not None:
        kwargs["language"] = language
    if model is not None:
        kwargs["model"] = model
    if device is not None:
        kwargs["device"] = device
    if autoStart is not None:
        kwargs["autoStart"] = autoStart
    if retention is not None:
        kwargs["retention"] = retention
    if theme is not None:
        kwargs["theme"] = theme
    if onboardingComplete is not None:
        kwargs["onboardingComplete"] = onboardingComplete
    if microphone is not None:
        kwargs["microphone"] = microphone
    if saveAudioToHistory is not None:
        kwargs["saveAudioToHistory"] = saveAudioToHistory
    # Hotkey settings
    if holdHotkey is not None:
        kwargs["holdHotkey"] = holdHotkey
    if holdHotkeyEnabled is not None:
        kwargs["holdHotkeyEnabled"] = holdHotkeyEnabled
    if toggleHotkey is not None:
        kwargs["toggleHotkey"] = toggleHotkey
    if toggleHotkeyEnabled is not None:
        kwargs["toggleHotkeyEnabled"] = toggleHotkeyEnabled

    # Check if onboarding was already complete before this update
    old_settings = controller.get_settings()
    was_onboarding_complete = old_settings.get("onboardingComplete", False)

    result = controller.update_settings(**kwargs)

    # If onboarding JUST NOW completed (was false, now true), trigger the callback
    if onboardingComplete is True and not was_onboarding_complete and _on_onboarding_complete:
        log.info("Onboarding completed, initializing popup")
        _on_onboarding_complete()

    return result


@server.method()
async def validate_hotkey(hotkey: str, excludeCurrent: Optional[str] = None):
    """Validate a hotkey string and check for conflicts with existing hotkeys.

    Args:
        hotkey: The hotkey string to validate (e.g., "ctrl+shift+r")
        excludeCurrent: Field to exclude from conflict check ("holdHotkey" or "toggleHotkey")

    Returns:
        {"valid": bool, "error": str or None, "conflicts": bool, "normalized": str}
    """
    from services.hotkey import validate_hotkey as do_validate, are_hotkeys_conflicting, normalize_hotkey

    # Validate format
    is_valid, error = do_validate(hotkey)
    if not is_valid:
        return {"valid": False, "error": error, "conflicts": False, "normalized": hotkey}

    # Normalize the hotkey to canonical format
    normalized = normalize_hotkey(hotkey)

    # Check for conflicts with existing hotkeys
    controller = get_controller()
    settings = controller.get_settings()

    conflicts = False
    conflict_with = None

    if excludeCurrent != "holdHotkey" and are_hotkeys_conflicting(normalized, settings.get("holdHotkey", "")):
        conflicts = True
        conflict_with = "Hold Mode"
    elif excludeCurrent != "toggleHotkey" and are_hotkeys_conflicting(normalized, settings.get("toggleHotkey", "")):
        conflicts = True
        conflict_with = "Toggle Mode"

    return {
        "valid": not conflicts,
        "error": f"Conflicts with {conflict_with} hotkey" if conflicts else None,
        "conflicts": conflicts,
        "normalized": normalized
    }


@server.method()
async def get_options():
    controller = get_controller()
    return controller.get_options()


@server.method()
async def get_gpu_info():
    """Get GPU/CUDA information."""
    controller = get_controller()
    return controller.get_gpu_info()


@server.method()
async def validate_device(device: str):
    """Validate a device setting before saving."""
    controller = get_controller()
    return controller.validate_device(device)


@server.method()
async def get_cudnn_download_info():
    """Get info about cuDNN download status."""
    controller = get_controller()
    return controller.get_cudnn_download_info()


# cuDNN download thread
_cudnn_download_thread: threading.Thread = None


@server.method()
async def download_cudnn():
    """Download and install cuDNN libraries in background thread."""
    global _cudnn_download_thread

    # Check if already downloading
    if _cudnn_download_thread and _cudnn_download_thread.is_alive():
        return {"success": True, "started": True, "alreadyRunning": True}

    controller = get_controller()

    def do_download():
        try:
            controller.download_cudnn()
        except Exception as e:
            log.error("cuDNN download thread error", error=str(e))

    # Start download in background thread
    _cudnn_download_thread = threading.Thread(target=do_download, daemon=True)
    _cudnn_download_thread.start()

    return {"success": True, "started": True}


@server.method()
async def get_cudnn_download_progress():
    """Get current cuDNN download progress."""
    controller = get_controller()
    return controller.get_cudnn_download_progress()


@server.method()
async def clear_cuda_libs():
    """Clear downloaded CUDA libraries (cuDNN + cuBLAS)."""
    controller = get_controller()
    return controller.clear_cuda_libs()


@server.method()
async def get_history(limit: int = 100, offset: int = 0, search: str = None, include_audio_meta: bool = False):
    controller = get_controller()
    return controller.get_history(limit, offset, search, include_audio_meta)


@server.method()
async def get_history_audio(history_id: int):
    controller = get_controller()
    return controller.get_history_audio(history_id)


@server.method()
async def get_stats():
    controller = get_controller()
    stats = controller.get_stats()
    return stats


@server.method()
async def delete_history(history_id: int):
    controller = get_controller()
    controller.delete_history(history_id)
    return {"success": True}


@server.method()
async def copy_to_clipboard(text: str):
    controller = get_controller()
    controller.clipboard_service.copy_to_clipboard(text)
    return {"success": True}


@server.method()
async def stop_recording():
    """Manually stop recording from the popup stop button."""
    controller = get_controller()
    controller.stop_recording()
    return {"success": True}


@server.method()
async def start_test_recording():
    """Start recording for onboarding test (no hotkey needed)."""
    controller = get_controller()
    controller.start_test_recording()
    return {"success": True}


@server.method()
async def stop_test_recording():
    """Stop test recording, transcribe, and return result (no paste/history)."""
    controller = get_controller()
    result = controller.stop_test_recording()
    return result


@server.method()
async def open_data_folder():
    """Open the application data folder."""
    controller = get_controller()
    controller.open_data_folder()
    return {"success": True}


@server.method()
async def open_external_url(url: str):
    """Open a URL in the system's default browser."""
    import webbrowser
    import sys
    import subprocess

    log.info("Opening external URL", url=url)

    try:
        # On Windows, os.startfile is more reliable than webbrowser in packaged apps
        if sys.platform == 'win32':
            import os
            os.startfile(url)
        elif sys.platform == 'darwin':
            # macOS
            subprocess.run(['open', url], check=True)
        else:
            # Linux and other platforms - try xdg-open first, fallback to webbrowser
            try:
                subprocess.run(['xdg-open', url], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                webbrowser.open(url)

        return {"success": True}
    except Exception as e:
        log.error("Failed to open external URL", url=url, error=str(e))
        # Fallback to webbrowser module
        try:
            webbrowser.open(url)
            return {"success": True}
        except Exception as fallback_error:
            log.error("Fallback browser open also failed", error=str(fallback_error))
            return {"success": False, "error": str(e)}


@server.method()
async def set_popup_enabled(enabled: bool):
    """Enable or disable the popup (used during onboarding)."""
    controller = get_controller()
    controller.set_popup_enabled(enabled)
    return {"success": True}


@server.method()
async def reset_all_data():
    """Reset all user data and return to onboarding state."""
    controller = get_controller()
    controller.reset_all_data()
    # Trigger callback to hide popup and show main window
    if _on_data_reset:
        _on_data_reset()
    return {"success": True}

# Window Management Callbacks
_window_actions = {
    "minimize": None,
    "maximize": None,
    "close": None
}

def register_window_actions(minimize_cb, maximize_cb, close_cb):
    _window_actions["minimize"] = minimize_cb
    _window_actions["maximize"] = maximize_cb
    _window_actions["close"] = close_cb

@server.method()
async def window_minimize():
    if _window_actions["minimize"]:
        _window_actions["minimize"]()
    return {"success": True}

@server.method()
async def window_toggle_maximize():
    if _window_actions["maximize"]:
        _window_actions["maximize"]()
    return {"success": True}

@server.method()
async def window_close():
    if _window_actions["close"]:
        _window_actions["close"]()
    return {"success": True}


# Model Management RPC Methods

@server.method()
async def get_model_info(model_name: str):
    """Get information about a model including cache status."""
    manager = get_model_manager()
    info = manager.get_model_info(model_name)
    return {
        "name": info.name,
        "sizeBytes": info.size_bytes,
        "cached": info.cached
    }


@server.method()
async def start_model_download(model_name: str):
    """Start downloading a model in the background.

    Progress updates are sent via 'download-progress' event.
    Completion is signaled via 'download-complete' event.
    """
    global _active_download_token, _download_thread

    # Cancel any existing download
    if _active_download_token and not _active_download_token.is_cancelled():
        model_log.info("Cancelling previous download for new request")
        _active_download_token.cancel()

    # Check if already cached
    manager = get_model_manager()
    if manager.is_model_cached(model_name):
        model_log.info("Model already cached", model=model_name)
        # Send immediate completion
        if _send_download_progress:
            _send_download_progress("download-complete", {
                "model": model_name,
                "success": True,
                "alreadyCached": True
            })
        return {"success": True, "alreadyCached": True}

    # Create new cancel token
    _active_download_token = CancelToken()

    def do_download():
        global _active_download_token

        def on_progress(progress: DownloadProgress):
            if _send_download_progress:
                _send_download_progress("download-progress", {
                    "model": progress.model_name,
                    "percent": progress.percent,
                    "downloadedBytes": progress.downloaded_bytes,
                    "totalBytes": progress.total_bytes,
                    "speedBps": progress.speed_bps,
                    "etaSeconds": progress.eta_seconds
                })

        try:
            success = manager.download_model(
                model_name,
                on_progress,
                _active_download_token
            )

            if _send_download_progress:
                _send_download_progress("download-complete", {
                    "model": model_name,
                    "success": success,
                    "cancelled": _active_download_token.is_cancelled()
                })
        except Exception as e:
            model_log.error("Download thread error", error=str(e))
            if _send_download_progress:
                _send_download_progress("download-complete", {
                    "model": model_name,
                    "success": False,
                    "error": str(e)
                })

    # Start download in background thread
    _download_thread = threading.Thread(target=do_download, daemon=True)
    _download_thread.start()

    model_log.info("Started model download", model=model_name)
    return {"success": True, "started": True}


@server.method()
async def cancel_model_download():
    """Cancel the current model download if any."""
    global _active_download_token

    if _active_download_token and not _active_download_token.is_cancelled():
        model_log.info("Cancelling model download")
        _active_download_token.cancel()
        return {"success": True, "cancelled": True}

    return {"success": True, "cancelled": False}


@server.method()
async def clear_model_cache():
    """Clear all cached Whisper models from the HuggingFace cache directory."""
    manager = get_model_manager()
    result = manager.clear_cache()
    return result
