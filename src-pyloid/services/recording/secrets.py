"""LLM API-key storage.

Primary path: OS keychain via the `keyring` package (Windows Credential Manager,
macOS Keychain, Linux Secret Service). Fallback when no backend is available:
JSON file at ~/.Dictore/secrets.json with mode 0600.

The secret never appears in settings rows, in logs, or in RPC responses — RPCs
expose a `has_api_key` boolean instead.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Optional

try:
    import keyring as _keyring  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - exercised in tests via monkeypatch
    _keyring = None  # type: ignore[assignment]


_SERVICE_NAME = "Dictore"
_USERNAME_PREFIX = "llm:"
_FALLBACK_PATH: Path = Path.home() / ".Dictore" / "secrets.json"


def _username(preset_or_endpoint: str) -> str:
    return f"{_USERNAME_PREFIX}{preset_or_endpoint}"


def _try_keyring(op, *args, **kwargs):
    """Run a keyring operation; return (ok, result). On any error return (False, None)."""
    if _keyring is None:
        return False, None
    try:
        return True, op(*args, **kwargs)
    except Exception:
        return False, None


# ---------- file fallback ----------

def _load_fallback() -> dict[str, str]:
    if not _FALLBACK_PATH.exists():
        return {}
    try:
        return json.loads(_FALLBACK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_fallback(data: dict[str, str]) -> None:
    _FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2)
    # Write atomically then chmod (best-effort).
    tmp = _FALLBACK_PATH.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(_FALLBACK_PATH)
    try:
        os.chmod(_FALLBACK_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except OSError:
        pass  # Windows or constrained FS — best-effort only.


# ---------- public API ----------

def set_api_key(preset: str, key: str) -> None:
    ok, _ = _try_keyring(_keyring.set_password, _SERVICE_NAME, _username(preset), key)
    if ok:
        return
    data = _load_fallback()
    data[preset] = key
    _write_fallback(data)


def get_api_key(preset: str) -> Optional[str]:
    ok, value = _try_keyring(_keyring.get_password, _SERVICE_NAME, _username(preset))
    if ok and value is not None:
        return value
    return _load_fallback().get(preset)


def has_api_key(preset: str) -> bool:
    return get_api_key(preset) is not None


def delete_api_key(preset: str) -> None:
    if _keyring is not None:
        try:
            _keyring.delete_password(_SERVICE_NAME, _username(preset))
        except Exception:
            # Either no backend, or no such entry — either way, fall through to the file.
            pass
    data = _load_fallback()
    if preset in data:
        data.pop(preset, None)
        _write_fallback(data)
