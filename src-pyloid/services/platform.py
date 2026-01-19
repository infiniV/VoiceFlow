"""Platform detection utilities for VoiceFlow.

Detects:
- Platform: linux, darwin, win32
- Display server: wayland, x11, macos, windows
- Available input tools: wtype, dotool, xdotool, ydotool, wl-copy, xclip
"""

import sys
import os
import shutil
from typing import Optional
from services.logger import get_logger

log = get_logger("platform")

# Cache for detected values
_platform_cache: dict = {}


def get_platform() -> str:
    """Get the current platform identifier.

    Returns:
        'linux', 'darwin', or 'win32'
    """
    return sys.platform


def get_display_server() -> str:
    """Detect the display server being used.

    Returns:
        'wayland', 'x11', 'macos', or 'windows'
    """
    if "display_server" in _platform_cache:
        return _platform_cache["display_server"]

    platform = get_platform()

    if platform == "win32":
        result = "windows"
    elif platform == "darwin":
        result = "macos"
    elif platform == "linux":
        # Check for Wayland first
        wayland_display = os.environ.get("WAYLAND_DISPLAY")
        xdg_session = os.environ.get("XDG_SESSION_TYPE", "").lower()

        if wayland_display or xdg_session == "wayland":
            result = "wayland"
        elif os.environ.get("DISPLAY"):
            result = "x11"
        else:
            # Fallback - assume X11 if we can't detect
            log.warning("Could not detect display server, assuming X11")
            result = "x11"
    else:
        # Unknown platform
        log.warning("Unknown platform", platform=platform)
        result = "unknown"

    _platform_cache["display_server"] = result
    log.info("Detected display server", display_server=result)
    return result


def find_tool(name: str) -> Optional[str]:
    """Find a tool by name using shutil.which.

    Args:
        name: The tool name (e.g., 'wtype', 'xdotool')

    Returns:
        Full path to the tool if found, None otherwise
    """
    return shutil.which(name)


def get_available_input_tools() -> list[str]:
    """Get list of available input tools for text input/clipboard.

    Returns:
        List of available tool names
    """
    if "input_tools" in _platform_cache:
        return _platform_cache["input_tools"]

    tools_to_check = [
        # Text input tools
        "wtype",      # Wayland text input
        "dotool",     # Universal (uinput-based)
        "xdotool",    # X11 text input
        "ydotool",    # Universal (uinput-based, works on Wayland)
        # Clipboard tools
        "wl-copy",    # Wayland clipboard (write)
        "wl-paste",   # Wayland clipboard (read)
        "xclip",      # X11 clipboard
        "xsel",       # X11 clipboard alternative
    ]

    available = []
    for tool in tools_to_check:
        if find_tool(tool):
            available.append(tool)

    _platform_cache["input_tools"] = available
    log.info("Detected input tools", tools=available)
    return available


def get_preferred_input_tool() -> Optional[str]:
    """Get the preferred input tool for the current display server.

    Tool priority (from Handy research):
    - Wayland: wtype → dotool → ydotool
    - X11: xdotool → ydotool

    Returns:
        Name of the preferred tool, or None if none available
    """
    display = get_display_server()
    available = get_available_input_tools()

    if display == "wayland":
        # Wayland priority: wtype → dotool → ydotool
        for tool in ["wtype", "dotool", "ydotool"]:
            if tool in available:
                return tool
    elif display == "x11":
        # X11 priority: xdotool → ydotool
        for tool in ["xdotool", "ydotool"]:
            if tool in available:
                return tool

    return None


def get_preferred_clipboard_tool() -> Optional[str]:
    """Get the preferred clipboard tool for the current display server.

    Returns:
        Name of the preferred clipboard tool, or None if none available
    """
    display = get_display_server()
    available = get_available_input_tools()

    if display == "wayland":
        # Wayland: prefer wl-copy/wl-paste
        if "wl-copy" in available:
            return "wl-copy"
    elif display == "x11":
        # X11: prefer xclip, fallback to xsel
        if "xclip" in available:
            return "xclip"
        if "xsel" in available:
            return "xsel"

    return None


def is_linux() -> bool:
    """Check if running on Linux."""
    return get_platform() == "linux"


def is_wayland() -> bool:
    """Check if running on Wayland display server."""
    return get_display_server() == "wayland"


def is_x11() -> bool:
    """Check if running on X11 display server."""
    return get_display_server() == "x11"


def get_platform_info() -> dict:
    """Get comprehensive platform information.

    Returns:
        Dictionary with platform, display_server, available_tools, etc.
    """
    platform = get_platform()
    display = get_display_server()
    tools = get_available_input_tools()
    preferred_input = get_preferred_input_tool()
    preferred_clipboard = get_preferred_clipboard_tool()

    # Determine if native hotkeys are supported
    # On Linux without root, the keyboard library may not work
    native_hotkeys_supported = platform == "win32" or platform == "darwin"
    if platform == "linux":
        # keyboard library requires root on Linux
        # Check if we're running as root (not recommended but possible)
        native_hotkeys_supported = os.geteuid() == 0 if hasattr(os, 'geteuid') else False

    return {
        "platform": platform,
        "displayServer": display,
        "availableTools": tools,
        "preferredInputTool": preferred_input,
        "preferredClipboardTool": preferred_clipboard,
        "nativeHotkeysSupported": native_hotkeys_supported,
        "signalHotkeysAvailable": platform != "win32",  # SIGUSR2 available on Unix
    }


def clear_cache():
    """Clear the platform detection cache (useful for testing)."""
    global _platform_cache
    _platform_cache = {}
