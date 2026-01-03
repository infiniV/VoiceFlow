import keyboard
from typing import Callable, Optional
import threading
from services.logger import get_logger

log = get_logger("hotkey")


# Canonical modifier order for consistent hotkey strings
# This order matches what the keyboard library expects
MODIFIER_ORDER = ['ctrl', 'alt', 'shift', 'win']
VALID_MODIFIERS = {'ctrl', 'alt', 'shift', 'win', 'windows', 'left windows', 'right windows'}


def normalize_hotkey(hotkey: str) -> str:
    """Normalize a hotkey string to a canonical format.

    Ensures consistent ordering: modifiers first (in MODIFIER_ORDER), then main keys.
    Also normalizes key names (e.g., 'windows' -> 'win').

    Example: 'r+win+ctrl' -> 'ctrl+win+r'
    """
    if not hotkey or not hotkey.strip():
        return hotkey

    parts = [p.strip().lower() for p in hotkey.split('+')]

    # Normalize key names
    normalized_parts = []
    for p in parts:
        if p in ('windows', 'left windows', 'right windows'):
            normalized_parts.append('win')
        elif p == 'control':
            normalized_parts.append('ctrl')
        else:
            normalized_parts.append(p)

    # Separate modifiers and main keys
    modifiers = []
    main_keys = []
    for p in normalized_parts:
        if p in {'ctrl', 'alt', 'shift', 'win'}:
            if p not in modifiers:  # Avoid duplicates
                modifiers.append(p)
        else:
            if p not in main_keys:  # Avoid duplicates
                main_keys.append(p)

    # Sort modifiers by canonical order
    modifiers.sort(key=lambda m: MODIFIER_ORDER.index(m) if m in MODIFIER_ORDER else 99)

    # Sort main keys alphabetically for consistency
    main_keys.sort()

    return '+'.join(modifiers + main_keys)


# Validation utilities
def validate_hotkey(hotkey: str) -> tuple[bool, str]:
    """Validate a hotkey string format.

    Returns (is_valid, error_message).

    Allows both:
    - modifier+key combos (e.g., "ctrl+r")
    - multiple modifiers (e.g., "ctrl+win") - these work with the keyboard library
    """
    if not hotkey or not hotkey.strip():
        return False, "Hotkey cannot be empty"

    parts = [p.strip().lower() for p in hotkey.split('+')]

    if len(parts) < 2:
        return False, "Hotkey must have at least two keys"

    # Normalize key names for validation
    normalized_parts = []
    for p in parts:
        if p in ('windows', 'left windows', 'right windows'):
            normalized_parts.append('win')
        elif p == 'control':
            normalized_parts.append('ctrl')
        else:
            normalized_parts.append(p)

    # Check that we have at least one modifier
    modifiers = [p for p in normalized_parts if p in {'ctrl', 'alt', 'shift', 'win'}]
    if not modifiers:
        return False, "Hotkey must include at least one modifier (Ctrl, Alt, Shift, or Win)"

    # Allow either:
    # 1. At least one modifier + at least one non-modifier key (e.g., "ctrl+r")
    # 2. At least two modifiers (e.g., "ctrl+win") - these are valid hotkeys
    main_keys = [p for p in normalized_parts if p not in {'ctrl', 'alt', 'shift', 'win'}]
    if not main_keys and len(modifiers) < 2:
        return False, "Hotkey must have at least two keys (modifier+key or multiple modifiers)"

    return True, ""


def are_hotkeys_conflicting(hotkey1: str, hotkey2: str) -> bool:
    """Check if two hotkeys conflict (are identical when normalized)."""
    if not hotkey1 or not hotkey2:
        return False

    return normalize_hotkey(hotkey1) == normalize_hotkey(hotkey2)


class HotkeyService:
    def __init__(self):
        # Callbacks
        self._on_activate: Optional[Callable[[], None]] = None
        self._on_deactivate: Optional[Callable[[], None]] = None

        # Recording state
        self._hold_active = False
        self._toggle_active = False
        self._running = False
        self._max_recording_timer: Optional[threading.Timer] = None

        # Hotkey configuration (defaults)
        self._hold_hotkey: str = "ctrl+win"
        self._hold_hotkey_enabled: bool = True
        self._toggle_hotkey: str = "ctrl+shift+win"
        self._toggle_hotkey_enabled: bool = False

    def set_callbacks(
        self,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None],
    ):
        """Set callbacks for hotkey activation and deactivation."""
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate

    def configure(
        self,
        hold_hotkey: str = None,
        hold_enabled: bool = None,
        toggle_hotkey: str = None,
        toggle_enabled: bool = None,
    ):
        """Update hotkey configuration and re-register handlers if running."""
        needs_restart = False

        # Normalize hotkeys before storing to ensure consistent format
        if hold_hotkey is not None:
            hold_hotkey = normalize_hotkey(hold_hotkey)
            if hold_hotkey != self._hold_hotkey:
                self._hold_hotkey = hold_hotkey
                needs_restart = True
        if hold_enabled is not None and hold_enabled != self._hold_hotkey_enabled:
            self._hold_hotkey_enabled = hold_enabled
            needs_restart = True
        if toggle_hotkey is not None:
            toggle_hotkey = normalize_hotkey(toggle_hotkey)
            if toggle_hotkey != self._toggle_hotkey:
                self._toggle_hotkey = toggle_hotkey
                needs_restart = True
        if toggle_enabled is not None and toggle_enabled != self._toggle_hotkey_enabled:
            self._toggle_hotkey_enabled = toggle_enabled
            needs_restart = True

        if needs_restart and self._running:
            log.info("Hotkey configuration changed, re-registering hotkeys")
            self._unregister_hotkeys()
            self._register_hotkeys()

    def _parse_hotkey_keys(self, hotkey: str) -> list[str]:
        """Parse hotkey string into individual key names for release monitoring."""
        parts = [k.strip().lower() for k in hotkey.split('+')]
        # Normalize windows key variants
        result = []
        for p in parts:
            if p in ('windows', 'left windows', 'right windows'):
                result.append('win')
            else:
                result.append(p)
        return result

    # Hold mode handlers
    def _on_hold_press(self):
        """Called when hold hotkey is pressed."""
        if self._hold_active or self._toggle_active:
            return  # Already recording in some mode

        self._hold_active = True
        log.info("Hold hotkey activated")
        if self._on_activate:
            self._on_activate()

    def _check_hold_release(self, event):
        """Check if hold hotkey should be deactivated on key release."""
        if not self._hold_active:
            return

        # Check if all required keys are still pressed
        keys = self._parse_hotkey_keys(self._hold_hotkey)
        all_pressed = True
        for key in keys:
            if key == 'win':
                # Check various windows key names
                if not (keyboard.is_pressed('win') or keyboard.is_pressed('windows')):
                    all_pressed = False
                    break
            elif not keyboard.is_pressed(key):
                all_pressed = False
                break

        if not all_pressed:
            log.debug("Hold key released", key=event.name)
            self._deactivate_hold()

    def _deactivate_hold(self):
        """Deactivate hold mode recording."""
        if not self._hold_active:
            return
        self._hold_active = False
        self._cancel_max_timer()
        log.info("Hold hotkey deactivated")
        if self._on_deactivate:
            self._on_deactivate()

    # Toggle mode handlers
    def _on_toggle_press(self):
        """Called when toggle hotkey is pressed - toggles recording state."""
        if self._hold_active:
            return  # Hold mode is active, ignore toggle

        if not self._toggle_active:
            # Start recording
            self._toggle_active = True
            log.info("Toggle hotkey activated - recording started")
            if self._on_activate:
                self._on_activate()
        else:
            # Stop recording
            self._deactivate_toggle()

    def _deactivate_toggle(self):
        """Deactivate toggle mode recording."""
        if not self._toggle_active:
            return
        self._toggle_active = False
        self._cancel_max_timer()
        log.info("Toggle hotkey deactivated - recording stopped")
        if self._on_deactivate:
            self._on_deactivate()

    # Timer management
    def _start_max_timer(self):
        """Start a timer to auto-stop recording after 60 seconds."""
        self._cancel_max_timer()
        self._max_recording_timer = threading.Timer(60.0, self._on_max_timer)
        self._max_recording_timer.daemon = True
        self._max_recording_timer.start()

    def _cancel_max_timer(self):
        """Cancel the max recording timer."""
        if self._max_recording_timer:
            self._max_recording_timer.cancel()
            self._max_recording_timer = None

    def _on_max_timer(self):
        """Called when max recording time is reached."""
        log.info("Max recording time reached (60s)")
        if self._hold_active:
            self._deactivate_hold()
        elif self._toggle_active:
            self._deactivate_toggle()

    # Hotkey registration
    def _register_hotkeys(self):
        """Register all enabled hotkeys."""
        if self._hold_hotkey_enabled and self._hold_hotkey:
            self._register_hold_hotkey()
        if self._toggle_hotkey_enabled and self._toggle_hotkey:
            self._register_toggle_hotkey()

    def _unregister_hotkeys(self):
        """Unregister all hotkeys and release handlers."""
        try:
            keyboard.unhook_all()
        except Exception as e:
            log.error("Failed to unregister hotkeys", error=str(e))

    def _register_hold_hotkey(self):
        """Register hold-to-record hotkey with press/release handling."""
        log.info("Registering hold hotkey", hotkey=self._hold_hotkey)
        try:
            keyboard.add_hotkey(self._hold_hotkey, self._on_hold_press, suppress=False)

            # Monitor key releases to detect when user lets go
            keys = self._parse_hotkey_keys(self._hold_hotkey)
            for key in keys:
                try:
                    keyboard.on_release_key(key, self._check_hold_release)
                    # Also register windows key variants
                    if key == 'win':
                        keyboard.on_release_key('windows', self._check_hold_release)
                        keyboard.on_release_key('left windows', self._check_hold_release)
                        keyboard.on_release_key('right windows', self._check_hold_release)
                except Exception as e:
                    log.warning("Failed to register release handler for key", key=key, error=str(e))

            log.info("Hold hotkey registered successfully", hotkey=self._hold_hotkey)
        except Exception as e:
            log.error("Failed to register hold hotkey", hotkey=self._hold_hotkey, error=str(e))
            # Don't crash - just log the error and continue without this hotkey

    def _register_toggle_hotkey(self):
        """Register toggle hotkey - single press toggles recording."""
        log.info("Registering toggle hotkey", hotkey=self._toggle_hotkey)
        try:
            keyboard.add_hotkey(self._toggle_hotkey, self._on_toggle_press, suppress=False)
            log.info("Toggle hotkey registered successfully", hotkey=self._toggle_hotkey)
        except Exception as e:
            log.error("Failed to register toggle hotkey", hotkey=self._toggle_hotkey, error=str(e))
            # Don't crash - just log the error and continue without this hotkey

    # Public API
    def start(self):
        """Start listening for hotkeys."""
        if self._running:
            return

        self._running = True
        self._register_hotkeys()

    def stop(self):
        """Stop listening for hotkeys."""
        self._running = False
        self._unregister_hotkeys()
        self._cancel_max_timer()
        self._hold_active = False
        self._toggle_active = False

    def force_deactivate(self):
        """Manually force deactivation of either mode."""
        log.debug("Force deactivate called")
        if self._hold_active:
            self._deactivate_hold()
        elif self._toggle_active:
            self._deactivate_toggle()

    def is_running(self) -> bool:
        """Return True if the hotkey service is running."""
        return self._running

    def is_recording(self) -> bool:
        """Return True if currently recording in either mode."""
        return self._hold_active or self._toggle_active

    def get_active_mode(self) -> Optional[str]:
        """Return current active mode ('hold', 'toggle') or None."""
        if self._hold_active:
            return "hold"
        elif self._toggle_active:
            return "toggle"
        return None
