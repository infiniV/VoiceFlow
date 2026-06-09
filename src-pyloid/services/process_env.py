"""Subprocess env sanitization for PyInstaller / AppImage builds.

When Dictore is run from a PyInstaller bundle (or AppImage), the bootloader
prepends `_internal/` to `LD_LIBRARY_PATH`. Any subprocess we spawn inherits
that env, which makes system binaries (xdg-open -> chromium, etc.) load our
bundled libs (libharfbuzz, libstdc++, …) instead of the system ones — usually
with a `symbol lookup error: undefined symbol: hb_calloc` style crash.

PyInstaller saves the original values as `LD_LIBRARY_PATH_ORIG` / `LD_PRELOAD_ORIG`
etc. so we can restore them when handing off to a system process.
"""
import os
import sys

_LD_VARS = (
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "DYLD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES",
    "PYTHONHOME",
    "PYTHONPATH",
)


def is_frozen() -> bool:
    return getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")


def system_env() -> dict:
    """Return os.environ with PyInstaller LD_* / PYTHON* injections undone.

    For each var: if a `<var>_ORIG` exists, restore it as `<var>`; otherwise
    drop `<var>` entirely. Always strip the `_ORIG` keys from the result.
    """
    env = os.environ.copy()
    for var in _LD_VARS:
        orig_key = f"{var}_ORIG"
        orig_val = env.pop(orig_key, None)
        if orig_val is not None and orig_val != "":
            env[var] = orig_val
        else:
            env.pop(var, None)
    return env
