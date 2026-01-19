import sys
import time
from services.logger import get_logger
from services import platform as plat

log = get_logger("clipboard")

# Conditionally import platform-specific modules
if sys.platform == "win32":
    import pyperclip
    import pyautogui


class ClipboardService:
    def __init__(self):
        self._linux_input = None

        if sys.platform == "win32":
            # Windows: use pyautogui
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.PAUSE = 0.05
        elif sys.platform == "linux":
            # Linux: use LinuxInputService
            from services.linux_input import get_linux_input_service
            self._linux_input = get_linux_input_service()
            log.info(
                "Clipboard service using Linux input",
                status=self._linux_input.get_status()
            )

    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard.

        Args:
            text: Text to copy to clipboard

        Returns:
            True if successful
        """
        if sys.platform == "win32":
            pyperclip.copy(text)
            return True
        elif sys.platform == "linux" and self._linux_input:
            return self._linux_input.copy_to_clipboard(text)
        elif sys.platform == "darwin":
            # macOS: use pyperclip (it handles pbcopy/pbpaste)
            import pyperclip
            pyperclip.copy(text)
            return True
        else:
            log.error("No clipboard method available for platform", platform=sys.platform)
            return False

    def get_clipboard(self) -> str:
        """Get current clipboard content.

        Returns:
            Clipboard text, or empty string on failure
        """
        try:
            if sys.platform == "win32":
                return pyperclip.paste()
            elif sys.platform == "linux" and self._linux_input:
                return self._linux_input.get_clipboard()
            elif sys.platform == "darwin":
                import pyperclip
                return pyperclip.paste()
            else:
                return ""
        except Exception as e:
            log.warning("Failed to get clipboard", error=str(e))
            return ""

    def paste_at_cursor(self, text: str) -> bool:
        """Copy text to clipboard and paste at current cursor position.

        This method:
        1. Saves the original clipboard content
        2. Copies the new text to clipboard
        3. Simulates Ctrl+V to paste
        4. Optionally restores original clipboard (currently disabled)

        Args:
            text: Text to paste

        Returns:
            True if successful
        """
        log.debug("Paste at cursor called", text_length=len(text))

        # Save current clipboard content
        try:
            original_clipboard = self.get_clipboard()
        except Exception:
            original_clipboard = ""

        # Copy our text to clipboard
        if not self.copy_to_clipboard(text):
            log.error("Failed to copy text to clipboard")
            return False

        log.debug("Text copied to clipboard")

        # Small delay to ensure clipboard is updated
        time.sleep(0.1)

        # Simulate Ctrl+V based on platform
        success = self._simulate_paste()

        if success:
            log.debug("Paste command sent successfully")
        else:
            log.error("Failed to send paste command")

        # Small delay before any potential restoration
        time.sleep(0.1)

        # Optionally restore original clipboard
        # Commented out as it may interfere with user expectation
        # self.copy_to_clipboard(original_clipboard)

        return success

    def _simulate_paste(self) -> bool:
        """Simulate Ctrl+V keystroke.

        Returns:
            True if successful
        """
        log.debug("Simulating Ctrl+V")

        if sys.platform == "win32":
            # Windows: use pyautogui
            try:
                pyautogui.hotkey('ctrl', 'v')
                return True
            except Exception as e:
                log.error("pyautogui paste failed", error=str(e))
                return False

        elif sys.platform == "linux":
            # Linux: use LinuxInputService
            if self._linux_input and self._linux_input.is_available():
                return self._linux_input.paste_from_clipboard()
            else:
                log.error("Linux input service not available")
                return False

        elif sys.platform == "darwin":
            # macOS: use pyautogui with 'command' key
            try:
                import pyautogui
                pyautogui.hotkey('command', 'v')
                return True
            except Exception as e:
                log.error("pyautogui paste failed on macOS", error=str(e))
                return False

        else:
            log.error("Unsupported platform for paste", platform=sys.platform)
            return False

    def type_text_directly(self, text: str) -> bool:
        """Type text directly without using clipboard (Linux only fallback).

        This can be used if clipboard-based pasting doesn't work.

        Args:
            text: Text to type

        Returns:
            True if successful
        """
        if sys.platform == "linux" and self._linux_input:
            return self._linux_input.type_text(text)
        else:
            log.warning("Direct text typing only available on Linux")
            return False

    def get_platform_status(self) -> dict:
        """Get status information about clipboard service capabilities.

        Returns:
            Dictionary with platform-specific information
        """
        status = {
            "platform": sys.platform,
            "method": "unknown",
        }

        if sys.platform == "win32":
            status["method"] = "pyautogui"
            status["available"] = True
        elif sys.platform == "linux":
            if self._linux_input:
                linux_status = self._linux_input.get_status()
                status["method"] = "linux_input"
                status["available"] = linux_status["available"]
                status["inputTool"] = linux_status["inputTool"]
                status["clipboardTool"] = linux_status["clipboardTool"]
                status["displayServer"] = linux_status["displayServer"]
            else:
                status["method"] = "none"
                status["available"] = False
        elif sys.platform == "darwin":
            status["method"] = "pyautogui"
            status["available"] = True

        return status
