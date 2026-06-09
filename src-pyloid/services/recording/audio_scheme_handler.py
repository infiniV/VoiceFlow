"""Qt glue for the dictore:// custom URL scheme.

Pure HTTP semantics live in `audio_scheme.py` (engine-free, unit-tested).
This module owns the `QWebEngineUrlSchemeHandler` subclass that translates
each `QWebEngineUrlRequestJob` into a call to `serve_audio_range()` and
replies with a `QBuffer`.

`registerScheme()` itself runs in `main.py` BEFORE the QApplication is
constructed — see the top of main.py for that registration. This handler
is then installed on the default profile after the Pyloid app is created.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtWebEngineCore import (
    QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler,
)

from services.logger import get_logger
from services.recording.audio_scheme import (
    resolve_recording_audio_url,
    serve_audio_range,
)


_log = get_logger("audio")


class DictoreAudioSchemeHandler(QWebEngineUrlSchemeHandler):
    """Serves dictore://recording/<file>.wav with HTTP Range support.

    The HTML5 <audio> element on MeetingDetailPage points at this URL; Qt
    intercepts the request and routes it here. Range requests are required
    for seek/scrub on long recordings — without them the browser refuses
    to expose the seek bar.
    """

    def __init__(self, data_root: Path) -> None:
        super().__init__()
        self._data_root = Path(data_root)

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:  # noqa: N802 (Qt name)
        try:
            url = job.requestUrl().toString()
            method_bytes = bytes(job.requestMethod()).decode("ascii", "replace").upper()
            if method_bytes not in ("GET", "HEAD"):
                job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
                return

            file_path = resolve_recording_audio_url(url, self._data_root)
            if file_path is None:
                _log.warning("dictore:// URL did not resolve", url=url)
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return

            range_header = self._get_range_header(job)
            response = serve_audio_range(file_path, range_header)

            if response.status == 404:
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            if response.status == 416:
                job.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
                return

            # Forward Range / Length / Accept-Ranges so the audio element
            # gets a real seek bar. Content-Type is passed via reply() arg
            # so we exclude it from the additional headers map.
            extra: dict[QByteArray, QByteArray] = {}
            for key, value in response.headers.items():
                if key.lower() == "content-type":
                    continue
                extra[QByteArray(key.encode("ascii"))] = QByteArray(value.encode("ascii"))
            try:
                job.setAdditionalResponseHeaders(extra)
            except Exception as e:
                # Older PySide6 builds may not accept this dict shape — fall
                # back silently. Range support degrades but playback still works.
                _log.debug("setAdditionalResponseHeaders skipped", error=str(e))

            buffer = QBuffer(parent=job)
            buffer.setData(QByteArray(response.body))
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)

            mime = response.headers.get("Content-Type", "audio/wav").encode("ascii")
            job.reply(QByteArray(mime), buffer)
        except Exception as e:
            _log.error("dictore:// request failed", error=str(e))
            try:
                job.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
            except Exception:
                pass

    @staticmethod
    def _get_range_header(job: QWebEngineUrlRequestJob) -> str | None:
        try:
            headers = job.requestHeaders()
        except Exception:
            return None
        # PySide6 returns a dict-like {QByteArray: QByteArray}.
        for key, value in headers.items():
            try:
                k = bytes(key).decode("ascii", "replace")
            except Exception:
                continue
            if k.lower() == "range":
                try:
                    return bytes(value).decode("ascii", "replace")
                except Exception:
                    return None
        return None
