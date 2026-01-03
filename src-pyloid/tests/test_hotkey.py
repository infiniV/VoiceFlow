import pytest
from services.hotkey import HotkeyService, normalize_hotkey, validate_hotkey, are_hotkeys_conflicting


class TestNormalizeHotkey:
    def test_simple_modifier_main_key(self):
        """Normalizes simple modifier+key combos."""
        assert normalize_hotkey("ctrl+r") == "ctrl+r"
        assert normalize_hotkey("alt+x") == "alt+x"
        assert normalize_hotkey("shift+a") == "shift+a"

    def test_reorders_modifiers_first(self):
        """Main key comes after modifiers."""
        assert normalize_hotkey("r+ctrl") == "ctrl+r"
        assert normalize_hotkey("x+alt+ctrl") == "ctrl+alt+x"

    def test_canonical_modifier_order(self):
        """Modifiers are ordered: ctrl, alt, shift, win."""
        assert normalize_hotkey("shift+ctrl+alt+win+x") == "ctrl+alt+shift+win+x"
        assert normalize_hotkey("win+shift+alt+ctrl+x") == "ctrl+alt+shift+win+x"

    def test_normalizes_windows_key_variants(self):
        """Normalizes 'windows', 'left windows', 'right windows' to 'win'."""
        assert normalize_hotkey("windows+ctrl") == "ctrl+win"
        assert normalize_hotkey("left windows+alt") == "alt+win"
        assert normalize_hotkey("right windows+shift") == "shift+win"

    def test_normalizes_control_to_ctrl(self):
        """Normalizes 'control' to 'ctrl'."""
        assert normalize_hotkey("control+r") == "ctrl+r"

    def test_removes_duplicate_modifiers(self):
        """Duplicate modifiers are removed."""
        assert normalize_hotkey("ctrl+ctrl+r") == "ctrl+r"

    def test_removes_duplicate_main_keys(self):
        """Duplicate main keys are removed."""
        assert normalize_hotkey("ctrl+r+r") == "ctrl+r"

    def test_multiple_main_keys_sorted_alphabetically(self):
        """Multiple main keys are sorted alphabetically."""
        assert normalize_hotkey("ctrl+b+a") == "ctrl+a+b"

    def test_different_orderings_normalize_to_same(self):
        """Different orderings of same keys normalize to same result."""
        expected = "ctrl+win+r"
        assert normalize_hotkey("ctrl+win+r") == expected
        assert normalize_hotkey("win+ctrl+r") == expected
        assert normalize_hotkey("r+win+ctrl") == expected
        assert normalize_hotkey("r+ctrl+win") == expected

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert normalize_hotkey("") == ""
        assert normalize_hotkey("   ") == "   "

    def test_preserves_case_insensitivity(self):
        """Keys are lowercased."""
        assert normalize_hotkey("CTRL+R") == "ctrl+r"
        assert normalize_hotkey("Ctrl+Win+X") == "ctrl+win+x"


class TestValidateHotkey:
    def test_valid_hotkey_with_modifier_and_key(self):
        """Valid hotkey with modifier and main key."""
        is_valid, error = validate_hotkey("ctrl+r")
        assert is_valid is True
        assert error == ""

    def test_valid_hotkey_multiple_modifiers(self):
        """Valid hotkey with multiple modifiers."""
        is_valid, error = validate_hotkey("ctrl+shift+r")
        assert is_valid is True

    def test_valid_hotkey_two_modifiers_only(self):
        """Two modifiers without main key is valid (e.g., ctrl+win)."""
        is_valid, error = validate_hotkey("ctrl+win")
        assert is_valid is True
        is_valid, error = validate_hotkey("ctrl+shift")
        assert is_valid is True

    def test_invalid_empty_hotkey(self):
        """Empty hotkey is invalid."""
        is_valid, error = validate_hotkey("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_invalid_single_key(self):
        """Single key without modifier is invalid."""
        is_valid, error = validate_hotkey("r")
        assert is_valid is False

    def test_invalid_single_modifier(self):
        """Single modifier is invalid (needs at least two keys)."""
        is_valid, error = validate_hotkey("ctrl")
        assert is_valid is False
        assert "two keys" in error.lower()


class TestAreHotkeysConflicting:
    def test_identical_hotkeys_conflict(self):
        """Identical hotkeys conflict."""
        assert are_hotkeys_conflicting("ctrl+r", "ctrl+r") is True

    def test_different_order_same_keys_conflict(self):
        """Same keys in different order conflict."""
        assert are_hotkeys_conflicting("ctrl+win+r", "win+ctrl+r") is True
        assert are_hotkeys_conflicting("r+ctrl+win", "ctrl+win+r") is True

    def test_different_hotkeys_no_conflict(self):
        """Different hotkeys don't conflict."""
        assert are_hotkeys_conflicting("ctrl+r", "ctrl+t") is False
        assert are_hotkeys_conflicting("ctrl+win", "ctrl+shift+win") is False

    def test_empty_hotkey_no_conflict(self):
        """Empty hotkey doesn't conflict with anything."""
        assert are_hotkeys_conflicting("", "ctrl+r") is False
        assert are_hotkeys_conflicting("ctrl+r", "") is False

    def test_windows_variants_conflict(self):
        """'win' and 'windows' variants conflict."""
        assert are_hotkeys_conflicting("ctrl+win", "ctrl+windows") is True


class TestHotkeyService:
    def test_initial_state_not_running(self):
        """Hotkey service starts in non-running state."""
        service = HotkeyService()
        assert service.is_running() == False

    def test_start_changes_state_to_running(self):
        """Starting the service changes state to running."""
        service = HotkeyService()
        service.start()

        assert service.is_running() == True

        # Cleanup
        service.stop()

    def test_stop_changes_state_to_not_running(self):
        """Stopping the service changes state back to not running."""
        service = HotkeyService()
        service.start()
        service.stop()

        assert service.is_running() == False

    def test_start_twice_is_idempotent(self):
        """Starting twice doesn't cause issues."""
        service = HotkeyService()
        service.start()
        service.start()  # Should not error

        assert service.is_running() == True

        # Cleanup
        service.stop()

    def test_stop_without_start_is_safe(self):
        """Stopping without starting doesn't cause issues."""
        service = HotkeyService()
        service.stop()  # Should not error

        assert service.is_running() == False

    def test_set_callbacks(self):
        """Can set activation and deactivation callbacks."""
        service = HotkeyService()

        activated = []
        deactivated = []

        def on_activate():
            activated.append(True)

        def on_deactivate():
            deactivated.append(True)

        # Should not raise
        service.set_callbacks(
            on_activate=on_activate,
            on_deactivate=on_deactivate,
        )

    def test_callbacks_are_optional(self):
        """Service works without callbacks set."""
        service = HotkeyService()
        service.start()

        # Should not raise when no callbacks are set
        import time
        time.sleep(0.1)

        service.stop()
