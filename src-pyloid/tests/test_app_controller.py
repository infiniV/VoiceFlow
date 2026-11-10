import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
from app_controller import AppController, get_controller


@pytest.fixture
def temp_db():
    """Create a temporary directory for test database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def controller(temp_db):
    """Create an AppController with test database."""
    from services.database import DatabaseService
    from services.settings import SettingsService
    from services.audio import AudioService
    from services.transcription import TranscriptionService
    from services.hotkey import HotkeyService
    from services.clipboard import ClipboardService

    ctrl = AppController.__new__(AppController)
    ctrl.db = DatabaseService(temp_db)
    ctrl.settings_service = SettingsService(ctrl.db)
    ctrl.audio_service = AudioService()
    ctrl.transcription_service = TranscriptionService()
    ctrl.hotkey_service = HotkeyService()
    ctrl.clipboard_service = ClipboardService()
    ctrl._on_recording_start = None
    ctrl._on_recording_stop = None
    ctrl._on_transcription_complete = None
    ctrl._on_amplitude = None
    ctrl._on_error = None
    ctrl._shutdown_done = False

    yield ctrl

    # Cleanup
    ctrl.hotkey_service.stop()


class TestAppController:
    def test_get_settings_returns_dict(self, controller):
        """get_settings returns a dictionary with all settings."""
        settings = controller.get_settings()

        assert isinstance(settings, dict)
        assert "language" in settings
        assert "model" in settings
        assert "autoStart" in settings
        assert "retention" in settings
        assert "theme" in settings
        assert "onboardingComplete" in settings

    def test_get_settings_uses_camel_case(self, controller):
        """Settings dict uses camelCase for frontend compatibility."""
        settings = controller.get_settings()

        # Should be camelCase, not snake_case
        assert "autoStart" in settings
        assert "auto_start" not in settings
        assert "onboardingComplete" in settings
        assert "onboarding_complete" not in settings

    def test_update_settings_changes_values(self, controller):
        """update_settings persists changes."""
        controller.update_settings(language="es", theme="dark")
        settings = controller.get_settings()

        assert settings["language"] == "es"
        assert settings["theme"] == "dark"

    def test_update_settings_accepts_camel_case(self, controller):
        """update_settings accepts camelCase keys."""
        controller.update_settings(autoStart=False, onboardingComplete=True)
        settings = controller.get_settings()

        assert settings["autoStart"] == False
        assert settings["onboardingComplete"] == True

    def test_first_settings_reload_enables_dictation(self, temp_db, tmp_path, monkeypatch):
        """A model downloaded after startup becomes ready without restarting."""
        from services.database import DatabaseService

        monkeypatch.setattr("app_controller.DatabaseService", lambda: DatabaseService(temp_db))
        monkeypatch.setattr("app_controller.MeetingsController", Mock())
        ctrl = AppController()
        assert ctrl.dictation.wait_for_model() == "absent"

        (tmp_path / "config.json").write_text("{}", encoding="utf-8")
        (tmp_path / "model.bin").write_bytes(b"weights")
        with patch("huggingface_hub.snapshot_download", return_value=str(tmp_path)), \
             patch("services.transcription.WhisperModel") as whisper:
            with pytest.raises(FileNotFoundError, match="incomplete"):
                ctrl.transcription_service.load_model("tiny", "cpu")
            whisper.assert_not_called()

            (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
            with patch("app_controller.threading.Thread") as thread:
                ctrl.update_settings(model="tiny", device="cpu")
                thread.call_args.kwargs["target"]()

            whisper.assert_called_once_with(str(tmp_path), device="cpu", compute_type="int8", local_files_only=True)
        assert ctrl.dictation.wait_for_model() == "ready"

    def test_get_history_returns_list(self, controller):
        """get_history returns a list."""
        history = controller.get_history()

        assert isinstance(history, list)

    def test_get_history_with_params(self, controller):
        """get_history accepts limit, offset, and search params."""
        # Add some history
        controller.db.add_history("Test transcription one")
        controller.db.add_history("Test transcription two")
        controller.db.add_history("Different text")

        # Test limit
        history = controller.get_history(limit=2)
        assert len(history) <= 2

        # Test search
        history = controller.get_history(search="transcription")
        assert all("transcription" in h["text"].lower() for h in history)

    def test_delete_history_removes_entry(self, controller):
        """delete_history removes the specified entry."""
        history_id = controller.db.add_history("To be deleted")

        controller.delete_history(history_id)

        history = controller.get_history()
        assert not any(h["id"] == history_id for h in history)

    def test_get_options_returns_all_options(self, controller):
        """get_options returns available models, languages, etc."""
        options = controller.get_options()

        assert "models" in options
        assert "languages" in options
        assert "retentionOptions" in options
        assert "themeOptions" in options

        assert "tiny" in options["models"]
        assert "auto" in options["languages"]

    def test_set_ui_callbacks(self, controller):
        """Can set UI callbacks."""
        called = []

        def on_start():
            called.append("start")

        def on_stop():
            called.append("stop")

        # Should not raise
        controller.set_ui_callbacks(
            on_recording_start=on_start,
            on_recording_stop=on_stop,
        )

    def test_shutdown_stops_hotkey_service(self, controller):
        """shutdown stops the hotkey service."""
        controller.hotkey_service.start()
        assert controller.hotkey_service.is_running() == True

        controller.shutdown()

        assert controller.hotkey_service.is_running() == False

    def test_shutdown_is_idempotent(self, controller):
        """shutdown can be called twice — wired from both aboutToQuit and the
        post-app.run() path in main.py."""
        controller.hotkey_service.start()
        controller.shutdown()
        # Second call must not raise; service must still be stopped.
        controller.shutdown()
        assert controller.hotkey_service.is_running() == False
