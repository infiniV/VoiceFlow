import sys
import os

# ============================================================================
# Linux: Preload CUDA libraries from nvidia pip packages before any CUDA imports
# ============================================================================
if sys.platform.startswith('linux'):
    def _preload_nvidia_libs():
        """Preload nvidia .so libs from pip packages so ctranslate2/faster-whisper can find them."""
        import ctypes
        venv_sp = os.path.join(sys.prefix, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
        nvidia_dir = os.path.join(venv_sp, 'nvidia')
        if not os.path.isdir(nvidia_dir):
            return
        for pkg in sorted(os.listdir(nvidia_dir)):
            lib_dir = os.path.join(nvidia_dir, pkg, 'lib')
            if not os.path.isdir(lib_dir):
                continue
            for f in sorted(os.listdir(lib_dir)):
                if f.endswith('.so') or '.so.' in f:
                    try:
                        ctypes.CDLL(os.path.join(lib_dir, f), mode=ctypes.RTLD_GLOBAL)
                    except OSError:
                        pass

    try:
        _preload_nvidia_libs()
    except Exception:
        pass  # Best-effort, don't crash on failure

    # Imported lazily because services/* depends on env that we still need to
    # configure below; keep the import inside the linux block so non-linux
    # platforms don't pay the cost.
    from services.process_env import system_env as _system_env_for_hyprctl

    def _setup_hyprland_window_rules():
        """Set Hyprland window rules for the popup overlay if running under Hyprland.

        On Wayland, Qt clients cannot position their own toplevels — `set_position()`
        is a silent no-op. We therefore rely on the compositor to place and pin the
        popup. These rules use `windowrulev2` with the correct matcher syntax
        `title:^(Recording)$`. The previous `windowrule "...,match:title Recording"`
        form was silently rejected by hyprctl (no `match:` keyword exists), which
        is why the popup spawned in the middle of the screen on production builds
        even though the Python coordinate math was correct.

        TODO(wayland-other-compositors): KDE and GNOME need wlr-layer-shell or
        equivalent to dock a window — there's no portable Wayland positioning API.
        Only Hyprland is handled here for now (the rest of the userbase is X11/win/mac).
        """
        if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            return
        import subprocess
        # `move 50%-w/2 100%-h-100` puts the popup horizontally centered and
        # 100 px above the bottom of the active monitor (matches the original
        # Python intent at main.py: popup_y = _screen_y + _screen_height - 100).
        rules = [
            "float,title:^(Recording)$",
            "pin,title:^(Recording)$",
            "noinitialfocus,title:^(Recording)$",
            "nofocus,title:^(Recording)$",
            "noborder,title:^(Recording)$",
            "noshadow,title:^(Recording)$",
            "noblur,title:^(Recording)$",
            "rounding 0,title:^(Recording)$",
            "opacity 1.0 override 1.0 override,title:^(Recording)$",
            "move onscreen 50%-w/2 100%-h-100,title:^(Recording)$",
        ]
        # Strip PyInstaller LD_LIBRARY_PATH/LD_PRELOAD before spawning
        # hyprctl — without this, the AppImage's bundled libstdc++ shadows
        # the system one and hyprctl fails with `GLIBCXX_3.4.32 not found`.
        env = _system_env_for_hyprctl()
        for rule in rules:
            try:
                result = subprocess.run(
                    ['hyprctl', 'keyword', 'windowrulev2', rule],
                    capture_output=True, timeout=2, text=True, env=env,
                )
                if result.returncode != 0:
                    print(f"[WARN] hyprctl rejected rule {rule!r}: {result.stderr.strip() or result.stdout.strip()}",
                          flush=True)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                break

    try:
        _setup_hyprland_window_rules()
    except Exception:
        pass

    # Disable accessibility scanning — major perf bottleneck on Linux with large HTML pages
    os.environ.setdefault('QTWEBENGINE_ENABLE_LINUX_ACCESSIBILITY', '0')

# ----------------------------------------------------------------------------
# Register the dictore:// custom URL scheme BEFORE QApplication is created.
# QWebEngineUrlScheme.registerScheme() is a no-op once QApplication exists.
# Pyloid's __init__ instantiates QApplication, so this MUST run before the
# `from pyloid import Pyloid` import below (its module init does NOT construct
# QApplication; only Pyloid(...) does).
#
# The HTML5 <audio> element on MeetingDetailPage builds URLs of the form
# `dictore://recording/<filename>.wav`. The matching handler subclass is
# in services.recording.audio_scheme_handler and is installed on the default
# QWebEngineProfile after Pyloid() returns.
# ----------------------------------------------------------------------------
from PySide6.QtWebEngineCore import QWebEngineUrlScheme

_vf_scheme = QWebEngineUrlScheme(b"dictore")
_vf_scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
# PortUnspecified is the default for newly-constructed schemes; PySide6's
# setDefaultPort wants a raw int (-1) rather than the SpecialPort enum, so
# we just leave it at the default to avoid the type-mismatch.
_vf_scheme.setFlags(
    QWebEngineUrlScheme.Flag.SecureScheme
    | QWebEngineUrlScheme.Flag.LocalAccessAllowed
    | QWebEngineUrlScheme.Flag.CorsEnabled
    | QWebEngineUrlScheme.Flag.ViewSourceAllowed
)
QWebEngineUrlScheme.registerScheme(_vf_scheme)

from pyloid.tray import TrayEvent
from pyloid.utils import get_production_path, is_production
from pyloid.serve import pyloid_serve
from pyloid import Pyloid

# Override QTWEBENGINE_CHROMIUM_FLAGS **after** importing pyloid. pyloid.pyloid
# unconditionally assigns this env var at module-import time (clobbering anything
# we set earlier with setdefault), so we re-assign here using direct `=` to win.
# Qt WebEngine reads this env var when QApplication is constructed (which happens
# inside `Pyloid(...)` below), so as long as our assignment lands before that,
# the flags take effect.
#
# We keep pyloid's three baseline flags and add the throttling-disable flags.
# We deliberately do NOT pass GL-control flags (--use-gl, --disable-gpu-sandbox,
# --enable-gpu-rasterization, etc.) here: by this point pyloid's import has
# already initialised Qt's GL platform negotiation, so forcing --use-gl=egl
# trips "Only --use-gl=angle is supported on this platform" and crashes startup
# on Wayland/NVIDIA. Those GPU flags were never actually taking effect before
# the clobber fix either — pyloid was wiping them — so the app has been running
# without them all along.
#
# The `--disable-background-timer-throttling --disable-renderer-backgrounding
# --disable-features=CalculateNativeWinOcclusion` flags are essential for the
# Meetings recorder: without them, Chromium throttles setInterval to ~once per
# minute when the Dictore window loses focus, freezing the timer and level
# meters even though the backend keeps recording. Same flags Discord, Slack, and
# VS Code use for the same reason.
#
# `--disable-background-networking` and `--disable-backgrounding-occluded-windows`
# cover a separate failure mode: Chromium tears down network sockets in
# backgrounded renderers, which made the dashboard's pyloid-js fetch() calls
# fail with "TypeError: Failed to fetch" after a few seconds — breaking the
# Stop & save button even while the popup pill (which uses the Qt JS bridge,
# not HTTP) kept updating correctly.
if sys.platform.startswith('linux'):
    # `--disable-features=` only takes ONE value when re-specified — multiple
    # `--disable-features` flags overwrite each other, so we comma-separate.
    # `IntensiveWakeUpThrottling` is the Chromium feature that kicks in after
    # ~5 min of session time and reduces timer wake-ups to ~1 Hz regardless of
    # `--disable-background-timer-throttling`. Without disabling it, the
    # Meetings dashboard freezes after a few minutes of recording even when
    # the window is in the foreground.
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (
        '--enable-features=WebRTCPipeWireCapturer '
        '--ignore-certificate-errors --allow-insecure-localhost '
        '--disable-background-timer-throttling '
        '--disable-renderer-backgrounding '
        '--disable-backgrounding-occluded-windows '
        '--disable-background-networking '
        '--disable-features=CalculateNativeWinOcclusion,IntensiveWakeUpThrottling'
    )
    print(f"[DEBUG] QTWEBENGINE_CHROMIUM_FLAGS = {os.environ['QTWEBENGINE_CHROMIUM_FLAGS']}", flush=True)

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QApplication, QWidget

from server import server, register_onboarding_complete_callback, register_data_reset_callback, register_window_actions, register_download_progress_callback, register_popup_visibility_callback
from app_controller import get_controller
from services.logger import setup_logging, get_logger

# Setup logging first thing
setup_logging()
log = get_logger("window")


# ============================================================================
# Thread-safe signal emitter for cross-thread UI updates
# ============================================================================
class ThreadSafeSignals(QObject):
    """Emits signals that can be connected to slots running on the main thread."""
    recording_started = Signal()
    recording_stopped = Signal()
    transcription_complete = Signal(str)
    amplitude_changed = Signal(float)
    # Meeting recorder state changes — payload is {state, durationMs}.
    # Routed to the popup window so the user sees a "MEETING" indicator
    # whenever the long-form recorder is active, distinct from PTT.
    meeting_state_changed = Signal(dict)


# Global signal emitter instance (created after QApplication)
_signals: ThreadSafeSignals = None


def init_signals():
    """Initialize the signal emitter - must be called after QApplication is created."""
    global _signals
    _signals = ThreadSafeSignals()


# ============================================================================
# Single Instance Check (Issue #4: Multiple tray icons)
# ============================================================================
# Windows mutex-based single instance check as backup to Pyloid's single_instance
# This prevents multiple tray icons when Pyloid's check fails or app crashes
_instance_mutex = None

def ensure_single_instance():
    """Ensure only one instance of Dictore runs at a time using Windows mutex."""
    global _instance_mutex

    if sys.platform != 'win32':
        return True  # Only implement Windows mutex for now

    try:
        import ctypes
        from ctypes import wintypes

        # Windows API constants
        ERROR_ALREADY_EXISTS = 183

        # Create a named mutex
        kernel32 = ctypes.windll.kernel32
        mutex_name = "Dictore_SingleInstance_Mutex"

        _instance_mutex = kernel32.CreateMutexW(None, False, mutex_name)

        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            log.warning("Another instance of Dictore is already running")
            # Try to focus the existing instance by finding its window
            try:
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, "Dictore")
                if hwnd:
                    # Show and bring to foreground
                    SW_RESTORE = 9
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetForegroundWindow(hwnd)
                    log.info("Focused existing Dictore window")
            except Exception as e:
                log.warning("Could not focus existing window", error=str(e))
            return False

        log.info("Single instance check passed - mutex acquired")
        return True

    except Exception as e:
        log.error("Single instance check failed", error=str(e))
        return True  # Allow running if check fails


# Check for existing instance before proceeding
if not ensure_single_instance():
    log.info("Exiting - another instance is running")
    sys.exit(0)

# Initialize app
# Reverting OpenGL attribute to standard
# from PySide6.QtCore import Qt, QCoreApplication
# QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

print("[DEBUG] Creating Pyloid app...", flush=True)
app = Pyloid(app_name="Dictore", single_instance=True, server=server)
print("[DEBUG] Pyloid app created", flush=True)

# Tray-resident daemon: closing the dashboard window must NOT quit the app.
# Qt's default is True, which combined with Qt WebEngine's built-in Ctrl+W
# turns "close window" into "kill the daemon" — global hotkey dies, model
# reloads on respawn. The tray "Quit" item remains the only true exit.
QApplication.instance().setQuitOnLastWindowClosed(False)

# Patch pyloid.Pyloid.get_window_by_id to bypass its cross-thread Qt
# roundtrip. pyloid-rpc validates the window_id on EVERY RPC request
# (rpc.py:518) by calling self.pyloid.get_window_by_id(request_id), which
# uses execute_command() — that emits a Qt signal to the main thread and
# runs a nested QEventLoop.exec() in the asyncio RPC thread, with NO
# timeout, waiting for the Qt main thread to reply. If the Qt main thread
# is even briefly busy (WebEngine IPC, queued window.invoke calls during
# an active meeting recording, etc.), the asyncio thread wedges forever
# and every subsequent RPC request stacks up in aiohttp's accept queue
# (observed in the field: LISTEN 4 128 with the Stop button dead while
# the writer thread + WebChannel kept ticking). The Qt-side handler is
# literally just `self.app.windows_dict.get(window_id)` (pyloid.py:2117,
# 597), so we can do it directly from the asyncio thread — dict.get() is
# atomic under the GIL.
import types as _types
def _fast_get_window_by_id(self, window_id):
    return self.app.windows_dict.get(window_id)
app.get_window_by_id = _types.MethodType(_fast_get_window_by_id, app)

# Install the dictore:// handler on the default profile. The scheme itself
# was registered above (before QApplication). The handler must outlive every
# request, so we hold a module-level reference — Qt holds a non-owning ref.
from PySide6.QtWebEngineCore import QWebEngineProfile
from services.recording.audio_scheme_handler import DictoreAudioSchemeHandler
_vf_audio_handler = DictoreAudioSchemeHandler(get_controller().meetings.data_root)
QWebEngineProfile.defaultProfile().installUrlSchemeHandler(b"dictore", _vf_audio_handler)
log.info("dictore:// scheme handler installed",
         data_root=str(get_controller().meetings.data_root))

print("[DEBUG] Setting icons...", flush=True)
app.set_icon(get_production_path("src-pyloid/icons/icon.png"))
app.set_tray_icon(get_production_path("src-pyloid/icons/icon.png"))
print("[DEBUG] Icons set", flush=True)

# Initialize thread-safe signals for cross-thread UI updates
# Must be done after Pyloid creates QApplication
init_signals()

# Initialize controller
print("[DEBUG] Initializing controller...", flush=True)
controller = get_controller()

# Store reference to popup window
popup_window = None
_popup_visible = True  # Tracks whether user wants the popup shown


def show_dashboard():
    app.show_and_focus_main_window()


def open_settings():
    app.show_and_focus_main_window()
    # Frontend will handle showing settings tab via URL hash or event


def stop_active_meeting():
    """Tray-menu fallback for stopping a meeting recording when the dashboard
    renderer's fetch is dead (Chromium freezes the QtWebEngine renderer's
    network pipeline after a while of being occluded/unfocused on this
    Wayland+NVIDIA stack). Runs directly in the Qt main thread, no HTTP
    involved — so this path is throttling-immune."""
    try:
        controller = get_controller()
        controller.meetings.stop()
        log.info("tray: stopped active meeting recording")
    except Exception as exc:
        # No active recording, or already stopped — both are fine, just log
        # so the user knows the click was acknowledged.
        log.info("tray: stop meeting no-op", error=str(exc))


# Tray setup
app.set_tray_actions({
    TrayEvent.DoubleClick: show_dashboard,
})

app.set_tray_menu_items([
    {"label": "Open Dashboard", "callback": show_dashboard},
    {"label": "Stop active recording", "callback": stop_active_meeting},
    {"label": "Settings", "callback": open_settings},
    {"label": "Quit", "callback": app.quit},
])


# Recording popup window management
import json
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import QApplication

# Popup dimensions for different states
POPUP_IDLE_WIDTH = 110
POPUP_IDLE_HEIGHT = 18
POPUP_ACTIVE_WIDTH = 190
POPUP_ACTIVE_HEIGHT = 50

# Screen info cache (for active monitor)
_screen_x = 0        # Monitor X offset
_screen_y = 0        # Monitor Y offset
_screen_width = 1920
_screen_height = 1080


def _is_hyprland() -> bool:
    return bool(os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'))


def _hypr_dispatch(*args: str) -> None:
    """Run `hyprctl dispatch ...`; no-op if not on Hyprland or hyprctl missing.

    Used at runtime to move/resize the floating popup whenever it changes
    state (idle ↔ active), since Qt's `set_position()` is silently dropped on
    Wayland — the compositor is the only authority on window placement.

    Subprocess env is scrubbed via services.process_env.system_env() so the
    AppImage's bundled libstdc++ doesn't shadow the system one and break
    hyprctl with `GLIBCXX_3.4.32 not found` symbol errors.
    """
    if not _is_hyprland():
        return
    import subprocess
    from services.process_env import system_env
    try:
        result = subprocess.run(
            ['hyprctl', 'dispatch', *args],
            capture_output=True, timeout=2, text=True, env=system_env(),
        )
        if result.returncode != 0:
            log.warning("hyprctl dispatch failed",
                        args=list(args),
                        stderr=(result.stderr or '').strip())
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning("hyprctl dispatch error", error=str(e))


def get_active_monitor_info():
    """Get the monitor where the cursor is currently located (for multi-monitor support)."""
    global _screen_x, _screen_y, _screen_width, _screen_height
    try:
        # Get cursor position to determine active monitor
        cursor_pos = QCursor.pos()

        # Find the screen containing the cursor
        screen = QApplication.screenAt(cursor_pos)
        if screen is None:
            # Fallback to primary screen
            screen = QApplication.primaryScreen()

        if screen:
            geometry = screen.geometry()
            _screen_x = geometry.x()
            _screen_y = geometry.y()
            _screen_width = geometry.width()
            _screen_height = geometry.height()
            log.info("Active monitor detected",
                     x=_screen_x, y=_screen_y,
                     width=_screen_width, height=_screen_height,
                     screen_name=screen.name())
        else:
            # Ultimate fallback
            _screen_x = 0
            _screen_y = 0
            _screen_width = 1920
            _screen_height = 1080
            log.warning("No screen detected, using defaults")
    except Exception as e:
        log.error("Failed to get active monitor info", error=str(e))


def get_screen_info():
    """Get and cache screen dimensions (legacy function, now uses active monitor)."""
    get_active_monitor_info()


def resize_popup(width: int, height: int):
    """Resize and reposition popup window."""
    global popup_window
    if popup_window is None or not _popup_visible:
        return

    try:
        # Resize the window (works on X11 / Windows / macOS).
        popup_window.set_size(width, height)

        # Recenter horizontally on active monitor, keep at bottom.
        # Use monitor offset (_screen_x, _screen_y) for multi-monitor support.
        popup_x = _screen_x + (_screen_width - width) // 2
        popup_y = _screen_y + _screen_height - 100
        popup_window.set_position(popup_x, popup_y)

        # Ensure stay-on-top is maintained after resize.
        # Also prevent resizing and make non-focusable to reduce blinking.
        qwindow = popup_window._window._window
        qwindow.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )
        # Re-apply translucent background (required after setWindowFlags).
        qwindow.setAttribute(Qt.WA_TranslucentBackground, True)
        # Prevent window resizing.
        qwindow.setFixedSize(width, height)
        qwindow.show()

        # Wayland fallback: ask the compositor to re-dock the existing window.
        # `set_position()` and `set_size()` above are no-ops on Wayland for
        # toplevels — the windowrulev2 from _setup_hyprland_window_rules() only
        # fires on initial map, so we have to dispatch the move/resize here too.
        _hypr_dispatch('resizewindowpixel', f'exact {width} {height},title:^(Recording)$')
        _hypr_dispatch('movewindowpixel', f'exact {popup_x} {popup_y},title:^(Recording)$')
    except Exception as e:
        log.error("Failed to resize popup", error=str(e))


def init_popup():
    """Initialize the recording popup."""
    global popup_window
    log.debug("init_popup called")

    try:
        if popup_window is None:
            # Get active monitor info (where cursor is) for multi-monitor support
            get_active_monitor_info()

            # Create window with idle size initially
            # frame=False makes it frameless, transparent=True enables transparency
            popup_window = app.create_window(
                title="Recording",
                width=POPUP_IDLE_WIDTH,
                height=POPUP_IDLE_HEIGHT,
                frame=False,
                transparent=True,
            )

            # Access internal Qt objects for transparency setup
            qwindow = popup_window._window._window
            webview = popup_window._window.web_view

            # CRITICAL: Enable translucent background on the window widget
            # This is required for proper transparency on Windows in production
            qwindow.setAttribute(Qt.WA_TranslucentBackground, True)

            # CRITICAL: Set background color BEFORE loading URL
            # Qt WebEngineView requires this order to avoid black/white background
            webview.page().setBackgroundColor(QColor(0, 0, 0, 0))

            # Load the URL
            if is_production() or os.path.exists(get_production_path("dist-front")):
                url = pyloid_serve(directory=get_production_path("dist-front"))
                popup_window.load_url(f"{url}#/popup")
            else:
                popup_window.load_url("http://localhost:5173#/popup")

            # Position at bottom center of active monitor
            # Use monitor offset (_screen_x, _screen_y) for multi-monitor support
            popup_x = _screen_x + (_screen_width - POPUP_IDLE_WIDTH) // 2
            popup_y = _screen_y + _screen_height - 100
            popup_window.set_position(popup_x, popup_y)

            # Set window flags for stay-on-top and no taskbar icon
            # WindowDoesNotAcceptFocus prevents stealing focus and reduces blinking
            qwindow.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |  # Prevents taskbar icon
                Qt.WindowDoesNotAcceptFocus  # Prevents focus stealing and blinking
            )

            # Prevent window resizing (Issue #2)
            qwindow.setFixedSize(POPUP_IDLE_WIDTH, POPUP_IDLE_HEIGHT)

            # Show the window
            popup_window.show()
            log.info("Popup window created and shown",
                     x=popup_x, y=popup_y,
                     monitor_offset_x=_screen_x, monitor_offset_y=_screen_y)

            # Wayland: enforce dock position once the window is mapped.
            # The windowrulev2 move rule fires on map, but we re-issue here in
            # case the rule registration race hasn't completed yet on first run.
            def _enforce_dock_position():
                _hypr_dispatch('resizewindowpixel',
                               f'exact {POPUP_IDLE_WIDTH} {POPUP_IDLE_HEIGHT},title:^(Recording)$')
                _hypr_dispatch('movewindowpixel',
                               f'exact {popup_x} {popup_y},title:^(Recording)$')

            QTimer.singleShot(100, _enforce_dock_position)

            # Send initial idle state after a brief delay to ensure page is loaded
            def send_initial_state():
                send_popup_event('popup-state', {'state': 'idle'})
                log.debug("Sent initial idle state to popup")

            QTimer.singleShot(200, send_initial_state)
        else:
            log.debug("Popup window already exists, skipping creation")
    except Exception as e:
        log.error("Failed to initialize popup", error=str(e))

def send_popup_event(name, detail):
    """Send event to popup window using Pyloid's invoke method."""
    global popup_window
    if popup_window:
        try:
            popup_window.invoke(name, detail)
        except Exception as e:
            log.error("Failed to send popup event", event=name, error=str(e))

def _on_recording_start_slot():
    """Slot: Actual recording start handler - runs on main thread via signal."""
    log.info("Recording started")
    # Re-detect which monitor the cursor is on (fixes multi-monitor sticky popup)
    get_active_monitor_info()
    # Resize to active size for recording
    resize_popup(POPUP_ACTIVE_WIDTH, POPUP_ACTIVE_HEIGHT)
    send_popup_event('popup-state', {'state': 'recording'})

def on_recording_start():
    """Called from hotkey thread - emits signal to main Qt thread."""
    if _signals:
        _signals.recording_started.emit()

def _on_recording_stop_slot():
    """Slot: Actual recording stop handler - runs on main thread via signal."""
    log.info("Recording stopped - processing")
    # Keep active size during processing
    send_popup_event('popup-state', {'state': 'processing'})

def on_recording_stop():
    """Called from hotkey thread - emits signal to main Qt thread."""
    if _signals:
        _signals.recording_stopped.emit()


def _on_meeting_state_slot(payload):
    """Slot: meeting recorder state event - runs on main thread via signal.

    Fans the event out to both windows over Qt WebChannel (`window.invoke`):
      - Popup: gets a translated `popup-state` event sized for the floating pill.
      - Dashboard: gets the raw `meeting-state` event (state + durationMs +
        recordingId + peak meters), used by MeetingRecorderContext in place of
        the old HTTP polling. This transport survives Chromium renderer
        freezes, which is the whole reason we moved off polling."""
    payload = payload or {}
    state = payload.get("state", "idle")
    duration_ms = int(payload.get("durationMs") or 0)

    # Dashboard gets the raw payload regardless of state — including idle,
    # so the recorder context can react to stop events too.
    send_main_window_event("meeting-state", payload)

    if state == "idle":
        # End of meeting — return popup to its normal idle.
        global _last_meeting_log_state
        _last_meeting_log_state = None
        log.info("Meeting ended", duration_ms=duration_ms)
        resize_popup(POPUP_IDLE_WIDTH, POPUP_IDLE_HEIGHT)
        send_popup_event("popup-state", {"state": "idle"})
        return
    # Throttle the popup-pill log line — the tick now fires this 4 Hz.
    # We only log on actual state transitions.
    _maybe_log_meeting_state(state, duration_ms)
    # Use the wider active pill so the duration counter has room.
    resize_popup(POPUP_ACTIVE_WIDTH, POPUP_ACTIVE_HEIGHT)
    send_popup_event(
        "popup-state",
        {
            "state": "meeting-recording" if state == "recording" else "meeting-paused",
            "durationMs": duration_ms,
        },
    )


# Tracks the last (state, popup-resize-bucket) we logged so the 4 Hz tick
# doesn't fill the log with identical lines. Only transitions are noisy.
_last_meeting_log_state: "str | None" = None


def _maybe_log_meeting_state(state: str, duration_ms: int) -> None:
    global _last_meeting_log_state
    if state == _last_meeting_log_state:
        return
    _last_meeting_log_state = state
    log.info("Meeting state", state=state, duration_ms=duration_ms)


def on_meeting_state(name, payload):
    """Called from MeetingsController's event_emitter on a background thread.
    Filters to meeting-state events and hands off to the main Qt thread."""
    if name != "meeting-state" or not _signals:
        return
    _signals.meeting_state_changed.emit(payload or {})

def _on_transcription_complete_slot(text: str):
    """Slot: Actual transcription complete handler - runs on main thread via signal."""
    log.info("Transcription complete", text_length=len(text))
    # Resize back to idle size
    resize_popup(POPUP_IDLE_WIDTH, POPUP_IDLE_HEIGHT)
    send_popup_event('popup-state', {'state': 'idle'})

def on_transcription_complete(text: str):
    """Called from transcription thread - emits signal to main Qt thread."""
    if _signals:
        _signals.transcription_complete.emit(text)

def send_main_window_event(name, detail):
    """Send event to main window using Pyloid's invoke method."""
    global window
    if window:
        try:
            window.invoke(name, detail)
        except Exception as e:
            log.error("Failed to send main window event", event=name, error=str(e))

def _on_amplitude_slot(amp: float):
    """Slot: Actual amplitude handler - runs on main thread via signal."""
    # Send to popup if it exists
    send_popup_event('amplitude', amp)
    # Also send to main window (for onboarding mic test)
    send_main_window_event('amplitude', amp)

def on_amplitude(amp: float):
    """Called from audio thread - emits signal to main Qt thread."""
    if _signals:
        _signals.amplitude_changed.emit(amp)


def on_onboarding_complete():
    """Called when user completes onboarding - hide main window, show popup."""
    global window
    log.info("Onboarding complete - initializing popup")
    # Hide the main window (user can reopen via tray)
    if window:
        window.hide()
    # Initialize the popup directly (QTimer doesn't work reliably from async RPC context)
    init_popup()


def hide_popup():
    """Hide the popup window (used when returning to onboarding)."""
    global popup_window
    log.debug("Hiding popup window")
    if popup_window:
        try:
            popup_window.hide()
            popup_window.close()
            popup_window = None
            log.info("Popup window hidden and destroyed")
        except Exception as e:
            log.error("Failed to hide popup", error=str(e))


def on_data_reset():
    """Called when user resets all data - show main window, hide popup."""
    global window
    log.info("Data reset - returning to onboarding")
    # Hide the popup
    hide_popup()
    # Show the main window for onboarding
    if window:
        window.show()
        try:
            qwindow = window._window._window
            qwindow.showMaximized()
        except Exception as e:
            log.error("Could not maximize window", error=str(e))


def send_download_progress(event_name: str, data: dict):
    """Send download progress events to the main window."""
    send_main_window_event(event_name, data)


def on_popup_visibility_changed(visible: bool):
    """Called when the showPopup setting changes."""
    global popup_window, _popup_visible
    _popup_visible = visible
    if visible:
        if popup_window is None:
            log.info("Popup visibility enabled - creating popup")
            init_popup()
        else:
            popup_window.show()
            log.info("Popup visibility enabled - showing popup")
    else:
        if popup_window is not None:
            popup_window.hide()
            log.info("Popup visibility disabled - hiding popup")


# Register callbacks
register_onboarding_complete_callback(on_onboarding_complete)
register_data_reset_callback(on_data_reset)
register_download_progress_callback(send_download_progress)
register_popup_visibility_callback(on_popup_visibility_changed)

# Connect thread-safe signals to their slot handlers
# Qt.QueuedConnection ensures slots run on the main thread
_signals.recording_started.connect(_on_recording_start_slot, Qt.QueuedConnection)
_signals.recording_stopped.connect(_on_recording_stop_slot, Qt.QueuedConnection)
_signals.transcription_complete.connect(_on_transcription_complete_slot, Qt.QueuedConnection)
_signals.amplitude_changed.connect(_on_amplitude_slot, Qt.QueuedConnection)
_signals.meeting_state_changed.connect(_on_meeting_state_slot, Qt.QueuedConnection)

# Set UI callbacks
controller.set_ui_callbacks(
    on_recording_start=on_recording_start,
    on_recording_stop=on_recording_stop,
    on_transcription_complete=on_transcription_complete,
    on_amplitude=on_amplitude,
)

# Route meeting recorder events to the popup (meeting-state pill).
controller.set_meetings_event_emitter(on_meeting_state)

# Initialize controller (load model, start hotkey listener)
print("[DEBUG] Initializing controller...", flush=True)
controller.initialize()
print("[DEBUG] Controller initialized", flush=True)


# Check if onboarding is complete
settings = controller.get_settings()
onboarding_complete = settings.get("onboardingComplete", False)
log.info("Startup", onboarding_complete=onboarding_complete)

# Get Screen Info for main window
get_screen_info()


# Window Control Functions
def minimize_main_window():
    if window:
        window._window._window.showMinimized()

def toggle_maximize_main_window():
    if window:
        qwin = window._window._window
        if qwin.isMaximized():
            qwin.showNormal()
        else:
            qwin.showMaximized()

def close_main_window():
    # Instead of quitting, we hide to tray if onboarding is done
    if window:
        window.hide()

# Register these actions with the server so RPC can call them
register_window_actions(minimize_main_window, toggle_maximize_main_window, close_main_window)


# Main window setup
print(f"[DEBUG] is_production={is_production()}", flush=True)
if is_production() or os.path.exists(get_production_path("dist-front")):
    print("[DEBUG] Serving dist-front...", flush=True)
    url = pyloid_serve(directory=get_production_path("dist-front"))
    print(f"[DEBUG] Served at {url}", flush=True)
    # Revert to standard frame, no transparency to fix crash
    print("[DEBUG] Creating main window...", flush=True)
    window = app.create_window(title="Dictore", frame=True, transparent=False, dev_tools=True)
    print("[DEBUG] Main window created", flush=True)
    window.load_url(url)
    print("[DEBUG] URL loaded", flush=True)
else:
    # Dev: Standard Frame
    window = app.create_window(title="Dictore", dev_tools=True, frame=True, transparent=False)
    # try:
    #     window._window.web_view.page().setBackgroundColor(QColor(0, 0, 0, 0))
    # except Exception as e:
    #     error(f"Failed to set transparent background: {e}")
    window.load_url("http://localhost:5173")

# Qt-level close (native title-bar X, Ctrl+W from Qt WebEngine) routes through
# Pyloid's BrowserWindow.closeEvent, which removes the window from
# app.windows_dict and unconditionally calls app.quit() once the dict is empty
# (.venv/.../pyloid/browser_window.py:1115). That bypasses
# setQuitOnLastWindowClosed(False) — confirmed in dev: with the popup hidden
# by preference, Ctrl+W on the dashboard fires app.quit() and the daemon dies.
# Override the QMainWindow's closeEvent so any Qt-level close just hides the
# window — matching the frontend's close_main_window RPC path. Tray "Quit"
# still calls app.quit() explicitly, so explicit exits are unaffected.
def _hide_main_window_on_close(event):
    event.ignore()
    if window:
        window.hide()
window._window._window.closeEvent = _hide_main_window_on_close

# Enforce Minimum Size Globally based on Screen Size
try:
    # Use cached screen info or default
    target_width = int(_screen_width * 0.8)
    target_height = int(_screen_height * 0.8)
    
    # Fallback if detection failed or is weird
    if target_width < 1024: target_width = 1280
    if target_height < 720: target_height = 800

    qwindow = window._window._window
    # Set Minimum Size to ensure it never gets "small" as requested
    qwindow.setMinimumSize(target_width, target_height)
    
    # Also set the initial size to this target
    window.set_size(target_width, target_height)
    
    log.info("Window sizing forced", width=target_width, height=target_height)
except Exception as e:
    log.error("Failed to set window size constraints", error=str(e))


if onboarding_complete:
    # Start minimized - user can open via tray icon
    log.info("Onboarding already complete - hiding window and scheduling popup init")
    window.hide()
    # Initialize popup after a short delay (if enabled in settings)
    show_popup = settings.get("showPopup", True)
    _popup_visible = show_popup
    if show_popup:
        QTimer.singleShot(500, init_popup)
    else:
        log.info("Popup hidden by user preference")
else:
    # Show maximized for onboarding experience
    window.show()
    log.info("Showing onboarding window")
    # Don't initialize popup during onboarding

# Tear down services BEFORE Qt destroys QApplication. CTranslate2's CUDA
# worker threads need to be joined while libcuda is still loaded — running
# this in aboutToQuit (Qt event loop still alive) avoids the SIGABRT race
# against libcuda's own atexit handler. The post-app.run() call below stays
# as a fallback for non-Qt exit paths; controller.shutdown() is idempotent.
QApplication.instance().aboutToQuit.connect(controller.shutdown)

print(f"[DEBUG] About to call app.run(), onboarding_complete={onboarding_complete}", flush=True)
app.run()
print("[DEBUG] app.run() returned", flush=True)

# Cleanup on exit
controller.shutdown()
