"""
Domain-based logging for Dictore.

Hybrid format: [timestamp] [LEVEL] [domain] message | {structured data}
File: ~/.Dictore/Dictore.log
Rotation: 100MB max, 1 backup (.log.1)
Domains: model, audio, hotkey, settings, database, clipboard, window

Usage:
    from services.logger import get_logger
    log = get_logger("model")
    log.info("Loading whisper-small")
    log.error("Download failed", error="Network timeout", url="https://...")
"""
import logging
import json
import re
import sys
from pathlib import Path
from typing import Optional, Any
from logging.handlers import RotatingFileHandler


# ---------- Secret redaction ----------
#
# Defensive measures so LLM API keys, bearer tokens, etc. never reach the log file
# or stderr — even when developers accidentally pass them as structured data.
#
# Two surfaces are covered:
#   * Free-text log messages — regex-based redaction (Bearer tokens, sk-* keys).
#   * Structured kwargs — key-name-based redaction (Authorization, api_key, …).

_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}\b")
_SK_TOKEN_RE = re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b")
_REDACTED = "***REDACTED***"
_SENSITIVE_KEYS = {
    "authorization",
    "api_key", "api-key", "apikey",
    "x_api_key", "x-api-key",
    "password", "token", "secret",
    "bearer",
}


def redact_text(message: str) -> str:
    """Mask secret-like substrings in a free-text log message."""
    if not isinstance(message, str):
        return message
    message = _BEARER_RE.sub(f"Bearer {_REDACTED}", message)
    message = _SK_TOKEN_RE.sub(_REDACTED, message)
    return message


def redact_structured(data: Any) -> Any:
    """Walk a dict/list and replace values under sensitive keys with REDACTED."""
    if isinstance(data, dict):
        out: dict = {}
        for key, value in data.items():
            if isinstance(key, str) and key.lower() in _SENSITIVE_KEYS:
                out[key] = _REDACTED
            else:
                out[key] = redact_structured(value)
        return out
    if isinstance(data, list):
        return [redact_structured(item) for item in data]
    if isinstance(data, str):
        return redact_text(data)
    return data


class RedactionFilter(logging.Filter):
    """Mutates LogRecord in place so handlers only see redacted content."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Free-text message (preserve args semantics: redact the final string).
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        redacted = redact_text(rendered)
        if redacted != rendered:
            record.msg = redacted
            record.args = ()  # already-formatted; don't let logging re-apply args

        # Structured data attached by DomainLogger.
        structured = getattr(record, "structured_data", None)
        if structured is not None:
            record.structured_data = redact_structured(structured)
        return True


# Configuration constants
LOG_MAX_BYTES = 100 * 1024 * 1024  # 100MB
LOG_BACKUP_COUNT = 1

# Valid domains
VALID_DOMAINS = {"model", "audio", "hotkey", "settings", "database", "clipboard", "window"}

# Global state
_initialized = False
_log_file: Optional[Path] = None
_domain_loggers: dict[str, "DomainLogger"] = {}
_file_handler: Optional[RotatingFileHandler] = None
_console_handler: Optional[logging.StreamHandler] = None


def get_default_log_path() -> Path:
    """Get the default log file path."""
    return Path.home() / ".Dictore" / "Dictore.log"


class HybridFormatter(logging.Formatter):
    """
    Formatter that produces hybrid format:
    [timestamp] [LEVEL] [domain] message | {structured data}

    The structured data is stored in the 'structured_data' attribute of the LogRecord.
    """

    def __init__(self):
        super().__init__()
        self.datefmt = '%Y-%m-%d %H:%M:%S'

    def format(self, record: logging.LogRecord) -> str:
        # Format timestamp
        timestamp = self.formatTime(record, self.datefmt)

        # Map level names (WARNING -> WARN for consistency with design)
        level = record.levelname
        if level == "WARNING":
            level = "WARN"

        # Get domain from logger name (format: Dictore.domain)
        parts = record.name.split('.')
        domain = parts[1] if len(parts) > 1 else "app"

        # Build base message
        base = f"[{timestamp}] [{level}] [{domain}] {record.getMessage()}"

        # Add structured data if present
        structured_data = getattr(record, 'structured_data', None)
        if structured_data:
            json_str = json.dumps(structured_data, ensure_ascii=False)
            return f"{base} | {json_str}"

        return base


class DomainLogger:
    """
    A logger for a specific domain that supports structured data via kwargs.

    Usage:
        log = get_logger("model")
        log.info("Loading model", model_name="small", load_time_ms=1234)
    """

    def __init__(self, domain: str, logger: logging.Logger):
        self._domain = domain
        self._logger = logger

    def _log(self, level: int, message: str, **kwargs):
        """Log a message with optional structured data."""
        # Create a LogRecord with structured data
        if kwargs:
            # Store kwargs as structured data
            extra = {'structured_data': kwargs}
        else:
            extra = {'structured_data': None}

        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log a debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log an info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log a warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log an error message."""
        self._log(logging.ERROR, message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log an exception with traceback. Call from within an except block."""
        if kwargs:
            extra = {'structured_data': kwargs}
        else:
            extra = {'structured_data': None}
        # Use logger.exception() which automatically captures exc_info
        self._logger.exception(message, extra=extra)


def setup_logging(
    log_file: Optional[Path] = None,
    max_bytes: int = LOG_MAX_BYTES,
    backup_count: int = LOG_BACKUP_COUNT
) -> None:
    """
    Initialize the logging system.

    Args:
        log_file: Path to log file. Defaults to ~/.Dictore/Dictore.log
        max_bytes: Maximum file size before rotation. Defaults to 100MB.
        backup_count: Number of backup files to keep. Defaults to 1.
    """
    global _initialized, _log_file, _file_handler, _console_handler

    if log_file is None:
        log_file = get_default_log_path()

    # Ensure directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    _log_file = log_file

    # Create formatter
    formatter = HybridFormatter()

    # Redaction filter applied to every handler so secrets never reach disk/stderr.
    redaction_filter = RedactionFilter()

    # Create file handler with rotation
    _file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(formatter)
    _file_handler.addFilter(redaction_filter)

    # Create console handler for development
    _console_handler = logging.StreamHandler(sys.stderr)
    _console_handler.setLevel(logging.DEBUG)
    _console_handler.setFormatter(formatter)
    _console_handler.addFilter(redaction_filter)

    # Set up root logger for Dictore
    root_logger = logging.getLogger("Dictore")
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(_file_handler)
    root_logger.addHandler(_console_handler)

    _initialized = True


def reset_logging() -> None:
    """
    Reset the logging system. Used for test isolation.
    """
    global _initialized, _log_file, _domain_loggers, _file_handler, _console_handler

    # Close handlers
    if _file_handler:
        _file_handler.close()
    if _console_handler:
        _console_handler.close()

    # Clear root logger
    root_logger = logging.getLogger("Dictore")
    root_logger.handlers.clear()

    # Clear all domain loggers
    for name in list(logging.Logger.manager.loggerDict.keys()):
        if name.startswith("Dictore."):
            logger = logging.getLogger(name)
            logger.handlers.clear()

    # Reset state
    _initialized = False
    _log_file = None
    _domain_loggers.clear()
    _file_handler = None
    _console_handler = None


def get_logger(domain: str) -> DomainLogger:
    """
    Get a logger for a specific domain.

    Args:
        domain: One of the valid domains (model, audio, hotkey, settings, database, clipboard, window)

    Returns:
        A DomainLogger instance for the specified domain.
    """
    global _domain_loggers

    # Return cached logger if exists
    if domain in _domain_loggers:
        return _domain_loggers[domain]

    # Auto-initialize if not done
    if not _initialized:
        setup_logging()

    # Create underlying Python logger
    logger_name = f"Dictore.{domain}"
    py_logger = logging.getLogger(logger_name)
    py_logger.setLevel(logging.DEBUG)

    # Create domain logger wrapper
    domain_logger = DomainLogger(domain, py_logger)
    _domain_loggers[domain] = domain_logger

    return domain_logger


# Legacy API compatibility - these are used by existing code
def debug(msg: str, *args, **kwargs):
    """Legacy debug function for backward compatibility."""
    get_logger("app").debug(msg)


def info(msg: str, *args, **kwargs):
    """Legacy info function for backward compatibility."""
    get_logger("app").info(msg)


def warning(msg: str, *args, **kwargs):
    """Legacy warning function for backward compatibility."""
    get_logger("app").warning(msg)


def error(msg: str, *args, **kwargs):
    """Legacy error function for backward compatibility."""
    get_logger("app").error(msg)


def exception(msg: str, *args, **kwargs):
    """Legacy exception function for backward compatibility."""
    get_logger("app").exception(msg)


# Legacy setup function
def setup_logger() -> logging.Logger:
    """Legacy setup function for backward compatibility."""
    setup_logging()
    return logging.getLogger("Dictore")


def get_log_dir() -> Path:
    """Legacy function to get log directory."""
    log_dir = Path.home() / ".Dictore"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
