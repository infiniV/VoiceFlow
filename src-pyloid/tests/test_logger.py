"""
Tests for the domain-based logging infrastructure.

Design requirements:
- Hybrid format: [timestamp] [LEVEL] [domain] message | {structured data}
- File: ~/.Dictore/Dictore.log
- Rotation: 100MB max, keeps 1 backup (.log.1)
- Domains: model, audio, hotkey, settings, database, clipboard, window
- Usage: get_logger("model") returns domain-specific logger
"""
import pytest
from pathlib import Path
import tempfile
import json
import re
from unittest.mock import patch


@pytest.fixture(autouse=True)
def reset_logger_state():
    """Reset logger state before and after each test."""
    from services.logger import reset_logging
    reset_logging()
    yield
    reset_logging()


@pytest.fixture
def temp_log_dir(reset_logger_state):
    """Create a temporary directory for log files.

    This fixture depends on reset_logger_state to ensure proper cleanup order:
    1. Test runs
    2. reset_logging() closes file handles
    3. temp_log_dir cleanup deletes files
    """
    from services.logger import reset_logging
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    # Close file handles before cleanup
    reset_logging()
    # Clean up manually
    import shutil
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass  # Best effort cleanup on Windows


class TestGetLogger:
    """Tests for get_logger() function."""

    def test_get_logger_returns_domain_logger(self):
        """get_logger('model') returns a logger for the model domain."""
        from services.logger import get_logger

        log = get_logger("model")

        assert log is not None
        assert hasattr(log, 'info')
        assert hasattr(log, 'error')
        assert hasattr(log, 'debug')
        assert hasattr(log, 'warning')

    def test_get_logger_same_domain_returns_same_instance(self):
        """Calling get_logger with same domain returns same logger instance."""
        from services.logger import get_logger

        log1 = get_logger("model")
        log2 = get_logger("model")

        assert log1 is log2

    def test_get_logger_different_domains_return_different_instances(self):
        """Different domains return different logger instances."""
        from services.logger import get_logger

        model_log = get_logger("model")
        audio_log = get_logger("audio")

        # They should be different logger instances
        assert model_log is not audio_log

    def test_all_domains_are_valid(self):
        """All specified domains can be used."""
        from services.logger import get_logger, VALID_DOMAINS

        # Design specifies these domains
        expected_domains = {"model", "audio", "hotkey", "settings", "database", "clipboard", "window"}

        assert VALID_DOMAINS == expected_domains

        # Each domain should return a valid logger
        for domain in expected_domains:
            log = get_logger(domain)
            assert log is not None


class TestLogFormat:
    """Tests for the hybrid log format."""

    def test_basic_log_format(self, temp_log_dir):
        """Log messages follow hybrid format: [timestamp] [LEVEL] [domain] message"""
        from services.logger import get_logger, setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        log = get_logger("model")
        log.info("Loading whisper-small")

        # Read log file
        content = log_file.read_text()

        # Check format: [2025-12-17 14:32:01] [INFO] [model] Loading whisper-small
        pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[INFO\] \[model\] Loading whisper-small'
        assert re.search(pattern, content), f"Expected format not found in: {content}"

    def test_log_with_structured_data(self, temp_log_dir):
        """Log with kwargs includes structured JSON data after pipe."""
        from services.logger import get_logger, setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        log = get_logger("model")
        log.error("Download failed", error="Network timeout", url="https://example.com")

        content = log_file.read_text()

        # Check format: [timestamp] [ERROR] [model] Download failed | {"error":"Network timeout","url":"https://..."}
        assert "[ERROR]" in content
        assert "[model]" in content
        assert "Download failed" in content
        assert "|" in content

        # Extract JSON part and verify it's valid
        match = re.search(r'\| ({.+})', content)
        assert match, f"Structured data not found in: {content}"

        data = json.loads(match.group(1))
        assert data["error"] == "Network timeout"
        assert data["url"] == "https://example.com"

    def test_log_without_structured_data_has_no_pipe(self, temp_log_dir):
        """Log without kwargs does not include pipe separator."""
        from services.logger import get_logger, setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        log = get_logger("model")
        log.info("Simple message")

        content = log_file.read_text()
        lines = [l for l in content.strip().split('\n') if 'Simple message' in l]
        assert len(lines) == 1

        # Should not have pipe separator for simple messages
        assert " | " not in lines[0]

    def test_all_log_levels(self, temp_log_dir):
        """All log levels work correctly."""
        from services.logger import get_logger, setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        log = get_logger("audio")
        log.debug("Debug message")
        log.info("Info message")
        log.warning("Warning message")
        log.error("Error message")

        content = log_file.read_text()

        assert "[DEBUG]" in content
        assert "[INFO]" in content
        assert "[WARN]" in content  # Design uses WARN not WARNING
        assert "[ERROR]" in content


class TestLogRotation:
    """Tests for log file rotation."""

    def test_log_file_location(self, temp_log_dir):
        """Log file is created at specified location."""
        from services.logger import setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        # Write something to ensure file is created
        from services.logger import get_logger
        log = get_logger("model")
        log.info("Test")

        assert log_file.exists()

    def test_rotation_max_bytes_is_100mb(self):
        """Rotation is configured for 100MB max size."""
        from services.logger import LOG_MAX_BYTES

        expected = 100 * 1024 * 1024  # 100MB
        assert LOG_MAX_BYTES == expected

    def test_rotation_keeps_one_backup(self):
        """Rotation keeps exactly 1 backup file."""
        from services.logger import LOG_BACKUP_COUNT

        assert LOG_BACKUP_COUNT == 1

    def test_rotation_creates_backup_file(self, temp_log_dir):
        """When log exceeds max size, backup is created with .log.1 extension."""
        from services.logger import setup_logging, get_logger

        log_file = temp_log_dir / "Dictore.log"
        # Use small max size for testing
        setup_logging(log_file, max_bytes=1000, backup_count=1)

        log = get_logger("model")

        # Write enough to trigger rotation
        for i in range(100):
            log.info(f"Message {i}: " + "x" * 50)

        # Check that backup was created
        backup_file = temp_log_dir / "Dictore.log.1"
        assert backup_file.exists(), "Backup file should be created after rotation"


class TestDefaultLogPath:
    """Tests for default log file path."""

    def test_default_log_path_is_in_dictore_dir(self):
        """Default log path is ~/.Dictore/Dictore.log"""
        from services.logger import get_default_log_path

        expected = Path.home() / ".Dictore" / "Dictore.log"
        assert get_default_log_path() == expected


class TestDomainLoggerInterface:
    """Tests for the DomainLogger interface."""

    def test_info_with_kwargs(self, temp_log_dir):
        """info() accepts keyword arguments for structured data."""
        from services.logger import get_logger, setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        log = get_logger("model")
        log.info("Model loaded", model_name="small", load_time_ms=1234)

        content = log_file.read_text()
        assert "model_name" in content
        assert "small" in content
        assert "load_time_ms" in content
        assert "1234" in content

    def test_error_with_kwargs(self, temp_log_dir):
        """error() accepts keyword arguments for structured data."""
        from services.logger import get_logger, setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        log = get_logger("audio")
        log.error("Recording failed", device_id=2, error_code="ACCESS_DENIED")

        content = log_file.read_text()
        assert "device_id" in content
        assert "error_code" in content
        assert "ACCESS_DENIED" in content

    def test_debug_with_kwargs(self, temp_log_dir):
        """debug() accepts keyword arguments for structured data."""
        from services.logger import get_logger, setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        log = get_logger("hotkey")
        log.debug("Key pressed", key="ctrl", state="down")

        content = log_file.read_text()
        assert "key" in content
        assert "ctrl" in content

    def test_warning_with_kwargs(self, temp_log_dir):
        """warning() accepts keyword arguments for structured data."""
        from services.logger import get_logger, setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        log = get_logger("settings")
        log.warning("Invalid value", setting="retention", value=-5)

        content = log_file.read_text()
        assert "setting" in content
        assert "retention" in content


class TestLoggerReset:
    """Tests for logger reset functionality (for testing isolation)."""

    def test_reset_logging_clears_state(self, temp_log_dir):
        """reset_logging() clears all logger state for test isolation."""
        from services.logger import get_logger, reset_logging, setup_logging

        log_file = temp_log_dir / "Dictore.log"
        setup_logging(log_file)

        log1 = get_logger("model")
        log1.info("Test")

        # Reset
        reset_logging()

        # After reset, setup should be needed again
        log_file2 = temp_log_dir / "Dictore2.log"
        setup_logging(log_file2)

        log2 = get_logger("model")
        log2.info("Test2")

        # New log should go to new file
        assert log_file2.exists()
        assert "Test2" in log_file2.read_text()
