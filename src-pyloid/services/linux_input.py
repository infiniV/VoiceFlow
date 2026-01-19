"""Linux input service for text input and clipboard operations.

Provides platform-specific text input and clipboard operations for Linux,
using external tools like wtype (Wayland), xdotool (X11), etc.

Tool priority (from Handy research):
- Wayland: wtype → dotool → ydotool
- X11: xdotool → ydotool
"""

import subprocess
import shlex
from typing import Optional
from services.logger import get_logger
from services import platform as plat

log = get_logger("linux_input")


class LinuxInputService:
    """Service for Linux text input and clipboard operations."""

    def __init__(self):
        self._input_tool: Optional[str] = None
        self._clipboard_tool: Optional[str] = None
        self._display_server: Optional[str] = None
        self._detect_tools()

    def _detect_tools(self):
        """Detect available tools and select the best ones."""
        self._display_server = plat.get_display_server()
        self._input_tool = plat.get_preferred_input_tool()
        self._clipboard_tool = plat.get_preferred_clipboard_tool()

        log.info(
            "Linux input service initialized",
            display_server=self._display_server,
            input_tool=self._input_tool,
            clipboard_tool=self._clipboard_tool,
        )

    def _run_command(self, cmd: list[str], input_text: str = None) -> tuple[bool, str]:
        """Run a command and return (success, output/error).

        Args:
            cmd: Command and arguments as a list
            input_text: Optional text to pipe to stdin

        Returns:
            Tuple of (success, output_or_error)
        """
        try:
            result = subprocess.run(
                cmd,
                input=input_text.encode() if input_text else None,
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True, result.stdout.decode().strip()
            else:
                error = result.stderr.decode().strip() or f"Exit code {result.returncode}"
                return False, error
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except FileNotFoundError:
            return False, f"Tool not found: {cmd[0]}"
        except Exception as e:
            return False, str(e)

    def type_text(self, text: str) -> bool:
        """Type text at the current cursor position.

        Args:
            text: Text to type

        Returns:
            True if successful, False otherwise
        """
        if not self._input_tool:
            log.error("No input tool available")
            return False

        log.debug("Typing text", tool=self._input_tool, text_length=len(text))

        success = False
        error = ""

        if self._input_tool == "wtype":
            # wtype -- "{text}" (-- prevents option parsing)
            success, error = self._run_command(["wtype", "--", text])

        elif self._input_tool == "dotool":
            # echo "type {text}" | dotool
            # Need to escape the text properly
            dotool_cmd = f"type {text}"
            success, error = self._run_command(["dotool"], input_text=dotool_cmd)

        elif self._input_tool == "xdotool":
            # xdotool type --clearmodifiers "{text}"
            success, error = self._run_command(["xdotool", "type", "--clearmodifiers", text])

        elif self._input_tool == "ydotool":
            # ydotool type "{text}"
            success, error = self._run_command(["ydotool", "type", text])

        else:
            log.error("Unknown input tool", tool=self._input_tool)
            return False

        if not success:
            log.error("Failed to type text", tool=self._input_tool, error=error)
        else:
            log.debug("Text typed successfully", tool=self._input_tool)

        return success

    def paste_from_clipboard(self) -> bool:
        """Simulate Ctrl+V to paste from clipboard.

        Returns:
            True if successful, False otherwise
        """
        if not self._input_tool:
            log.error("No input tool available for paste")
            return False

        log.debug("Simulating paste", tool=self._input_tool)

        success = False
        error = ""

        if self._input_tool == "wtype":
            # wtype -M ctrl v -m ctrl (press ctrl, type v, release ctrl)
            success, error = self._run_command(["wtype", "-M", "ctrl", "v", "-m", "ctrl"])

        elif self._input_tool == "dotool":
            # dotool: key ctrl+v
            success, error = self._run_command(["dotool"], input_text="key ctrl+v")

        elif self._input_tool == "xdotool":
            # xdotool key --clearmodifiers ctrl+v
            success, error = self._run_command(["xdotool", "key", "--clearmodifiers", "ctrl+v"])

        elif self._input_tool == "ydotool":
            # ydotool key 29:1 47:1 47:0 29:0 (ctrl down, v down, v up, ctrl up)
            # Key codes: ctrl=29, v=47
            success, error = self._run_command(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])

        else:
            log.error("Unknown input tool", tool=self._input_tool)
            return False

        if not success:
            log.error("Failed to paste", tool=self._input_tool, error=error)
        else:
            log.debug("Paste successful", tool=self._input_tool)

        return success

    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard.

        Args:
            text: Text to copy

        Returns:
            True if successful, False otherwise
        """
        if not self._clipboard_tool:
            log.error("No clipboard tool available")
            return False

        log.debug("Copying to clipboard", tool=self._clipboard_tool, text_length=len(text))

        success = False
        error = ""

        if self._clipboard_tool == "wl-copy":
            # wl-copy reads from stdin
            success, error = self._run_command(["wl-copy"], input_text=text)

        elif self._clipboard_tool == "xclip":
            # xclip -selection clipboard
            success, error = self._run_command(
                ["xclip", "-selection", "clipboard"],
                input_text=text
            )

        elif self._clipboard_tool == "xsel":
            # xsel --clipboard --input
            success, error = self._run_command(
                ["xsel", "--clipboard", "--input"],
                input_text=text
            )

        else:
            log.error("Unknown clipboard tool", tool=self._clipboard_tool)
            return False

        if not success:
            log.error("Failed to copy to clipboard", tool=self._clipboard_tool, error=error)
        else:
            log.debug("Copied to clipboard", tool=self._clipboard_tool)

        return success

    def get_clipboard(self) -> str:
        """Get current clipboard content.

        Returns:
            Clipboard text, or empty string on failure
        """
        log.debug("Getting clipboard content")

        success = False
        result = ""

        if self._clipboard_tool == "wl-copy":
            # wl-paste for reading
            if plat.find_tool("wl-paste"):
                success, result = self._run_command(["wl-paste", "-n"])
            else:
                log.warning("wl-paste not found, cannot read clipboard")
                return ""

        elif self._clipboard_tool == "xclip":
            # xclip -selection clipboard -o
            success, result = self._run_command(
                ["xclip", "-selection", "clipboard", "-o"]
            )

        elif self._clipboard_tool == "xsel":
            # xsel --clipboard --output
            success, result = self._run_command(
                ["xsel", "--clipboard", "--output"]
            )

        else:
            log.warning("No clipboard tool available for reading")
            return ""

        if not success:
            log.warning("Failed to get clipboard", error=result)
            return ""

        return result

    def is_available(self) -> bool:
        """Check if Linux input service has the required tools.

        Returns:
            True if at least input tool is available
        """
        return self._input_tool is not None

    def get_status(self) -> dict:
        """Get status information about the service.

        Returns:
            Dictionary with tool availability and names
        """
        return {
            "displayServer": self._display_server,
            "inputTool": self._input_tool,
            "clipboardTool": self._clipboard_tool,
            "available": self.is_available(),
        }


# Singleton instance
_service: Optional[LinuxInputService] = None


def get_linux_input_service() -> LinuxInputService:
    """Get the singleton LinuxInputService instance."""
    global _service
    if _service is None:
        _service = LinuxInputService()
    return _service
