"""
Tests for the Model Manager service.

Design requirements:
- is_model_cached(model_name) -> bool: Check if model exists in cache
- get_model_info(model_name) -> ModelInfo: Get model metadata (size, cache status)
- download_model(model_name, on_progress, cancel_token) -> bool: Download with progress
- load_model(model_name) -> WhisperModel: Load already-downloaded model
- ensure_model_ready(model_name, on_progress, cancel_token) -> WhisperModel: Download if needed + load

Data classes:
- DownloadProgress: model_name, percent, downloaded_bytes, total_bytes, speed_bps, eta_seconds
- ModelInfo: name, size_bytes, cached
- CancelToken: cancel(), is_cancelled()
"""
import pytest
from dataclasses import dataclass
from unittest.mock import Mock, patch, MagicMock
from typing import Callable, Optional


class TestCancelToken:
    """Tests for CancelToken class."""

    def test_cancel_token_initial_state_is_not_cancelled(self):
        """CancelToken starts in non-cancelled state."""
        from services.model_manager import CancelToken

        token = CancelToken()

        assert token.is_cancelled() is False

    def test_cancel_sets_cancelled_state(self):
        """Calling cancel() sets the cancelled state."""
        from services.model_manager import CancelToken

        token = CancelToken()
        token.cancel()

        assert token.is_cancelled() is True

    def test_cancel_is_idempotent(self):
        """Calling cancel() multiple times is safe."""
        from services.model_manager import CancelToken

        token = CancelToken()
        token.cancel()
        token.cancel()
        token.cancel()

        assert token.is_cancelled() is True


class TestModelInfo:
    """Tests for ModelInfo dataclass."""

    def test_model_info_fields(self):
        """ModelInfo has required fields."""
        from services.model_manager import ModelInfo

        info = ModelInfo(name="small", size_bytes=500_000_000, cached=True)

        assert info.name == "small"
        assert info.size_bytes == 500_000_000
        assert info.cached is True


class TestDownloadProgress:
    """Tests for DownloadProgress dataclass."""

    def test_download_progress_fields(self):
        """DownloadProgress has required fields."""
        from services.model_manager import DownloadProgress

        progress = DownloadProgress(
            model_name="small",
            percent=58.0,
            downloaded_bytes=270_000_000,
            total_bytes=466_000_000,
            speed_bps=1_500_000,
            eta_seconds=131
        )

        assert progress.model_name == "small"
        assert progress.percent == 58.0
        assert progress.downloaded_bytes == 270_000_000
        assert progress.total_bytes == 466_000_000
        assert progress.speed_bps == 1_500_000
        assert progress.eta_seconds == 131


class TestModelSizes:
    """Tests for model size reference data."""

    def test_model_sizes_defined(self):
        """MODEL_SIZES contains all expected faster-whisper models with approximate sizes."""
        from services.model_manager import MODEL_SIZES

        # Multilingual models
        assert "tiny" in MODEL_SIZES
        assert "base" in MODEL_SIZES
        assert "small" in MODEL_SIZES
        assert "medium" in MODEL_SIZES
        assert "large-v1" in MODEL_SIZES
        assert "large-v2" in MODEL_SIZES
        assert "large-v3" in MODEL_SIZES
        assert "turbo" in MODEL_SIZES

        # English-only models
        assert "tiny.en" in MODEL_SIZES
        assert "base.en" in MODEL_SIZES
        assert "small.en" in MODEL_SIZES
        assert "medium.en" in MODEL_SIZES

        # Distilled models
        assert "distil-small.en" in MODEL_SIZES
        assert "distil-medium.en" in MODEL_SIZES
        assert "distil-large-v2" in MODEL_SIZES
        assert "distil-large-v3" in MODEL_SIZES

        # Verify approximate sizes (within reasonable range)
        assert 50_000_000 < MODEL_SIZES["tiny"] < 100_000_000
        assert 100_000_000 < MODEL_SIZES["base"] < 200_000_000
        assert 400_000_000 < MODEL_SIZES["small"] < 600_000_000

    def test_get_available_models(self):
        """get_available_models returns list of all supported models."""
        from services.model_manager import ModelManager

        manager = ModelManager()
        models = manager.get_available_models()

        assert isinstance(models, list)
        assert len(models) == 16  # Total number of models
        assert "tiny" in models
        assert "turbo" in models
        assert "distil-large-v3" in models


class TestModelManager:
    """Tests for ModelManager class."""

    @pytest.fixture
    def model_manager(self):
        """Create a ModelManager instance for testing."""
        from services.model_manager import ModelManager
        return ModelManager()

    def test_is_model_cached_returns_false_for_uncached_model(self, model_manager):
        """is_model_cached returns False when model is not in cache."""
        # Use a fake model name that can't possibly be cached
        result = model_manager.is_model_cached("nonexistent-fake-model-xyz123")
        assert result is False

    def test_get_model_info_returns_model_info(self, model_manager):
        """get_model_info returns ModelInfo with correct fields."""
        from services.model_manager import ModelInfo

        info = model_manager.get_model_info("small")

        assert isinstance(info, ModelInfo)
        assert info.name == "small"
        assert info.size_bytes > 0
        # cached state depends on whether model was previously downloaded

    def test_get_model_info_includes_cached_status(self, model_manager):
        """get_model_info correctly reports cache status."""
        info = model_manager.get_model_info("tiny")

        assert isinstance(info.cached, bool)
        # The actual value depends on whether tiny was downloaded before

    def test_download_model_accepts_progress_callback(self, model_manager):
        """download_model accepts an on_progress callback."""
        from services.model_manager import CancelToken, DownloadProgress

        progress_updates = []

        def on_progress(progress: DownloadProgress):
            progress_updates.append(progress)

        token = CancelToken()

        # This test just verifies the signature, not actual download
        # We'll use a mock to avoid actual downloads in unit tests
        with patch.object(model_manager, '_do_download') as mock_download:
            mock_download.return_value = True
            model_manager.download_model("tiny", on_progress, token)

            # Verify _do_download was called with correct args
            mock_download.assert_called_once()

    def test_download_model_respects_cancellation(self, model_manager):
        """download_model returns False when cancelled."""
        from services.model_manager import CancelToken

        token = CancelToken()
        token.cancel()  # Cancel immediately

        with patch.object(model_manager, '_do_download') as mock_download:
            # Should not even call _do_download if already cancelled
            result = model_manager.download_model("tiny", lambda p: None, token)

            assert result is False
            mock_download.assert_not_called()

    def test_download_model_returns_true_on_success(self, model_manager):
        """download_model returns True when download completes successfully."""
        from services.model_manager import CancelToken

        token = CancelToken()

        with patch.object(model_manager, '_do_download', return_value=True):
            result = model_manager.download_model("tiny", lambda p: None, token)

            assert result is True

    def test_download_model_returns_false_on_cancel(self, model_manager):
        """download_model returns False when cancelled during download."""
        from services.model_manager import CancelToken

        token = CancelToken()

        # Simulate cancellation during download
        with patch.object(model_manager, '_do_download', return_value=False):
            result = model_manager.download_model("tiny", lambda p: None, token)

            assert result is False


class TestModelManagerIntegration:
    """Integration tests that may require actual model operations.

    These tests are slower as they may involve actual file system operations.
    """

    @pytest.fixture
    def model_manager(self):
        """Create a ModelManager instance for testing."""
        from services.model_manager import ModelManager
        return ModelManager()

    def test_is_model_cached_detects_cached_tiny_model(self, model_manager):
        """is_model_cached correctly detects if tiny model is cached.

        Note: This test's result depends on whether tiny was downloaded before.
        It primarily tests that the method runs without error and uses
        faster_whisper's download_model with local_files_only=True internally.
        """
        result = model_manager.is_model_cached("tiny")
        assert isinstance(result, bool)


class TestProgressCallback:
    """Tests for progress callback behavior."""

    def test_progress_callback_receives_all_fields(self):
        """Progress callback receives DownloadProgress with all fields populated."""
        from services.model_manager import DownloadProgress, ModelManager, CancelToken

        manager = ModelManager()
        received_progress = []

        def on_progress(progress: DownloadProgress):
            received_progress.append(progress)

        # Mock the internal download to send progress updates
        def mock_download(model_name, on_progress, cancel_token):
            # Simulate progress updates
            on_progress(DownloadProgress(
                model_name=model_name,
                percent=50.0,
                downloaded_bytes=250_000_000,
                total_bytes=500_000_000,
                speed_bps=1_000_000,
                eta_seconds=250
            ))
            return True

        with patch.object(manager, '_do_download', mock_download):
            manager.download_model("small", on_progress, CancelToken())

        assert len(received_progress) >= 1
        p = received_progress[0]
        assert p.model_name == "small"
        assert p.percent == 50.0
        assert p.downloaded_bytes > 0
        assert p.total_bytes > 0
        assert p.speed_bps >= 0
        assert p.eta_seconds >= 0
