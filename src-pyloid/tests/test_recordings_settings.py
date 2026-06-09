"""Tests for slice 2 — recordings + LLM settings, secret storage, log redaction."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from services.database import DatabaseService
from services.settings import (
    DEFAULT_LLM_PROMPT,
    LLM_PRESETS,
    SettingsService,
)
from services.recording import secrets as secrets_mod
from services.logger import (
    RedactionFilter,
    get_logger,
    redact_text,
    redact_structured,
    reset_logging,
    setup_logging,
)


# ---------- settings ----------

@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield DatabaseService(Path(tmpdir) / "test.db")


@pytest.fixture
def settings_service(db):
    return SettingsService(db)


class TestRecordingsSettings:
    def test_defaults(self, settings_service):
        s = settings_service.get_settings()
        assert s.recordings_mic_device is None
        assert s.recordings_loopback_device is None
        assert s.recordings_auto_transcribe is True
        assert s.recordings_auto_summarize is False

    def test_update_round_trip(self, settings_service):
        settings_service.update_settings(
            recordings_mic_device="USB Mic",
            recordings_loopback_device="Built-in.monitor",
            recordings_auto_transcribe=False,
            recordings_auto_summarize=True,
        )
        s = settings_service.get_settings()
        assert s.recordings_mic_device == "USB Mic"
        assert s.recordings_loopback_device == "Built-in.monitor"
        assert s.recordings_auto_transcribe is False
        assert s.recordings_auto_summarize is True

    def test_persists_across_instances(self, db):
        SettingsService(db).update_settings(recordings_auto_summarize=True)
        assert SettingsService(db).get_settings().recordings_auto_summarize is True


class TestLLMSettings:
    def test_defaults(self, settings_service):
        s = settings_service.get_settings()
        assert s.llm_preset == "ollama"
        assert s.llm_endpoint == "http://localhost:11434/v1"
        assert s.llm_model == "llama3.2"
        assert s.llm_prompt_template == DEFAULT_LLM_PROMPT

    def test_update_round_trip(self, settings_service):
        settings_service.update_settings(
            llm_preset="openai",
            llm_endpoint="https://api.openai.com/v1",
            llm_model="gpt-4o-mini",
            llm_prompt_template="custom prompt {transcript}",
        )
        s = settings_service.get_settings()
        assert s.llm_preset == "openai"
        assert s.llm_endpoint == "https://api.openai.com/v1"
        assert s.llm_model == "gpt-4o-mini"
        assert s.llm_prompt_template == "custom prompt {transcript}"

    def test_known_presets(self):
        # The presets list is the source of truth for the frontend dropdown.
        assert set(LLM_PRESETS) == {"openai", "groq", "openrouter", "ollama", "custom"}


# ---------- secrets ----------

@pytest.fixture
def secrets_in_tempdir(tmp_path, monkeypatch):
    """Point the file fallback at a temp dir; we still let keyring be patched per-test."""
    monkeypatch.setattr(secrets_mod, "_FALLBACK_PATH", tmp_path / "secrets.json")
    yield tmp_path


class _FakeKeyring:
    """In-memory keyring stand-in. Mimics keyring.set/get/delete_password."""

    class errors:
        class PasswordDeleteError(Exception):
            pass

    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def get_password(self, service, username):
        return self.store.get((service, username))

    def delete_password(self, service, username):
        try:
            del self.store[(service, username)]
        except KeyError as exc:
            raise self.errors.PasswordDeleteError() from exc


class _BrokenKeyring:
    """Simulates keyring backend unavailability."""

    class errors:
        class PasswordDeleteError(Exception):
            pass

    def set_password(self, *a, **k):
        raise RuntimeError("no keyring backend")

    def get_password(self, *a, **k):
        raise RuntimeError("no keyring backend")

    def delete_password(self, *a, **k):
        raise RuntimeError("no keyring backend")


class TestSecretsKeyring:
    def test_set_get_round_trip(self, secrets_in_tempdir, monkeypatch):
        fake = _FakeKeyring()
        monkeypatch.setattr(secrets_mod, "_keyring", fake)
        secrets_mod.set_api_key("openai", "sk-abc123xyz")
        assert secrets_mod.get_api_key("openai") == "sk-abc123xyz"

    def test_has_api_key(self, secrets_in_tempdir, monkeypatch):
        fake = _FakeKeyring()
        monkeypatch.setattr(secrets_mod, "_keyring", fake)
        assert secrets_mod.has_api_key("openai") is False
        secrets_mod.set_api_key("openai", "sk-abc")
        assert secrets_mod.has_api_key("openai") is True

    def test_delete_api_key(self, secrets_in_tempdir, monkeypatch):
        fake = _FakeKeyring()
        monkeypatch.setattr(secrets_mod, "_keyring", fake)
        secrets_mod.set_api_key("openai", "sk-abc")
        secrets_mod.delete_api_key("openai")
        assert secrets_mod.get_api_key("openai") is None

    def test_delete_missing_is_silent(self, secrets_in_tempdir, monkeypatch):
        fake = _FakeKeyring()
        monkeypatch.setattr(secrets_mod, "_keyring", fake)
        # Not previously set — must not raise.
        secrets_mod.delete_api_key("openai")


class TestSecretsFileFallback:
    def test_set_uses_file_when_keyring_broken(self, secrets_in_tempdir, monkeypatch):
        monkeypatch.setattr(secrets_mod, "_keyring", _BrokenKeyring())
        secrets_mod.set_api_key("openai", "sk-fallback")
        assert (secrets_in_tempdir / "secrets.json").exists()
        # And reading it back works.
        assert secrets_mod.get_api_key("openai") == "sk-fallback"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes only")
    def test_fallback_file_is_chmod_600(self, secrets_in_tempdir, monkeypatch):
        monkeypatch.setattr(secrets_mod, "_keyring", _BrokenKeyring())
        secrets_mod.set_api_key("openai", "sk-x")
        mode = os.stat(secrets_in_tempdir / "secrets.json").st_mode & 0o777
        assert mode == 0o600

    def test_fallback_file_format_is_json(self, secrets_in_tempdir, monkeypatch):
        monkeypatch.setattr(secrets_mod, "_keyring", _BrokenKeyring())
        secrets_mod.set_api_key("openai", "sk-1")
        secrets_mod.set_api_key("groq", "gsk-2")
        data = json.loads((secrets_in_tempdir / "secrets.json").read_text())
        assert data["openai"] == "sk-1"
        assert data["groq"] == "gsk-2"

    def test_fallback_delete_removes_only_target_key(self, secrets_in_tempdir, monkeypatch):
        monkeypatch.setattr(secrets_mod, "_keyring", _BrokenKeyring())
        secrets_mod.set_api_key("openai", "a")
        secrets_mod.set_api_key("groq", "b")
        secrets_mod.delete_api_key("openai")
        assert secrets_mod.get_api_key("openai") is None
        assert secrets_mod.get_api_key("groq") == "b"


# ---------- log redaction ----------

class TestRedactionHelpers:
    def test_bearer_token_redacted(self):
        out = redact_text("Authorization: Bearer sk-abc123xyz456")
        assert "sk-abc123xyz456" not in out
        assert "REDACTED" in out

    def test_sk_token_standalone_redacted(self):
        out = redact_text("got key sk-abcdef1234567890")
        assert "sk-abcdef1234567890" not in out

    def test_short_sk_not_redacted(self):
        # Don't redact short strings that happen to start with "sk-" — they're not API keys.
        out = redact_text("path sk-1")
        assert "sk-1" in out

    def test_redact_text_passthrough_when_clean(self):
        assert redact_text("just a normal log line") == "just a normal log line"

    def test_redact_structured_authorization_value(self):
        out = redact_structured({"Authorization": "Bearer sk-xyz789abcdef"})
        assert "sk-xyz789abcdef" not in json.dumps(out)
        assert out["Authorization"] == "***REDACTED***"

    def test_redact_structured_api_key_value(self):
        out = redact_structured({"api_key": "sk-supersecret1234"})
        assert out["api_key"] == "***REDACTED***"

    def test_redact_structured_token_value(self):
        out = redact_structured({"token": "abc.def.ghi.jkl.mno"})
        assert out["token"] == "***REDACTED***"

    def test_redact_structured_preserves_unrelated_fields(self):
        out = redact_structured({"user": "alice", "api_key": "sk-1234567890abcdef"})
        assert out["user"] == "alice"

    def test_redact_structured_recurses_into_nested(self):
        out = redact_structured({"headers": {"Authorization": "Bearer xyzlongkey1234567"}})
        assert out["headers"]["Authorization"] == "***REDACTED***"


class TestRedactionFilter:
    def test_filter_redacts_message(self):
        filt = RedactionFilter()
        import logging as _logging
        rec = _logging.LogRecord(
            name="Dictore.llm",
            level=_logging.INFO,
            pathname="x.py", lineno=1,
            msg="POST with Bearer sk-shouldhide12345",
            args=None, exc_info=None,
        )
        filt.filter(rec)
        assert "sk-shouldhide12345" not in rec.getMessage()

    def test_filter_redacts_structured_data(self):
        filt = RedactionFilter()
        import logging as _logging
        rec = _logging.LogRecord(
            name="Dictore.llm",
            level=_logging.INFO,
            pathname="x.py", lineno=1,
            msg="sending request", args=None, exc_info=None,
        )
        rec.structured_data = {"Authorization": "Bearer sk-xyzabcdef123456"}
        filt.filter(rec)
        assert rec.structured_data["Authorization"] == "***REDACTED***"


class TestLoggerIntegration:
    def test_secrets_never_reach_log_file(self, tmp_path):
        """End-to-end: a log call containing 'Bearer sk-...' must not appear unredacted in the file."""
        reset_logging()
        log_file = tmp_path / "out.log"
        setup_logging(log_file=log_file)
        log = get_logger("llm")
        log.info("calling LLM", Authorization="Bearer sk-thisshouldbehidden9999")
        log.info("plain Bearer sk-anotherhiddenkey99999 in message")
        # Flush the file handler.
        reset_logging()

        content = log_file.read_text()
        assert "sk-thisshouldbehidden9999" not in content
        assert "sk-anotherhiddenkey99999" not in content
        assert "REDACTED" in content
