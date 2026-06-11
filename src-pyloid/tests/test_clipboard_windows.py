import sys

from services.clipboard import ClipboardService


def test_windows_paste_uses_keyboard_send(monkeypatch):
    sent = []

    class Keyboard:
        @staticmethod
        def send(keys):
            sent.append(keys)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "keyboard", Keyboard)

    ClipboardService()._simulate_paste_keystroke()

    assert sent == ["ctrl+v"]
