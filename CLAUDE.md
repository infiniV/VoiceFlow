# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VoiceFlow is a cross-platform voice-to-text paste utility built with Pyloid (Python desktop framework using PySide6/Qt WebEngine) and React. Users hold a hotkey to record audio, release to transcribe using faster-whisper, and the text is automatically pasted at the cursor. Supports Windows, Linux (Wayland/X11), and macOS.

## Commands

```bash
# Initial setup (installs both Node and Python dependencies)
pnpm run setup

# Development mode (runs Vite frontend + Pyloid backend concurrently)
pnpm run dev

# Development with hot-reload for Python changes
pnpm run dev:watch

# Build desktop application
pnpm run build

# Build platform installers (run on each target OS)
pnpm run build:installer          # Windows (.exe via Inno Setup)
pnpm run build:installer:linux    # Linux (.tar.gz + .AppImage)
pnpm run build:installer:macos    # macOS (.dmg)

# Run Python tests
cd VoiceFlow && uv run -p .venv pytest src-pyloid/tests/

# Run single test file
uv run -p .venv pytest src-pyloid/tests/test_transcription.py -v

# Run frontend only (for UI development)
pnpm run vite

# Lint frontend
pnpm run lint
```

## Architecture

### Backend (src-pyloid/)

Python backend using Pyloid framework with PySide6:

- **main.py** - Application entry point. Creates Pyloid app, tray icon, main dashboard window, and recording popup window. Sets up UI callbacks connecting backend events to popup state changes.
- **server.py** - RPC server using `PyloidRPC`. Exposes methods (`get_settings`, `update_settings`, `get_history`, etc.) that frontend calls via `pyloid-js` RPC.
- **app_controller.py** - Singleton controller orchestrating all services. Handles hotkey activate/deactivate flow: start recording -> stop recording -> transcribe -> paste at cursor -> save to history.

**Services (src-pyloid/services/):**
- `audio.py` - Microphone recording using sounddevice, streams amplitude for visualizer
- `transcription.py` - faster-whisper model loading and transcription
- `hotkey.py` - Global hotkey listener using keyboard library
- `clipboard.py` - Clipboard operations and paste-at-cursor using pyautogui
- `settings.py` - Settings management with defaults
- `database.py` - SQLite database for settings and history (stored at ~/.VoiceFlow/VoiceFlow.db)
- `logger.py` - Domain-based logging with hybrid format `[timestamp] [LEVEL] [domain] message | {json}`. Supports domains: model, audio, hotkey, settings, database, clipboard, window. Configured with 100MB log rotation.
- `model_manager.py` - Whisper model download/cache management using huggingface_hub. Provides download progress tracking (percent, speed, ETA), cancellation via CancelToken, daemon thread execution, and `clear_cache()` to delete only VoiceFlow's faster-whisper models.

### Frontend (src/)

React 18 + TypeScript + Vite frontend:

- **App.tsx** - Hash-based routing between `/popup`, `/onboarding`, and `/dashboard`. Checks model cache on startup and shows recovery modal if model is missing.
- **lib/api.ts** - RPC wrapper using `pyloid-js` to call Python backend methods. Includes model management APIs (`getModelInfo`, `startModelDownload`, `cancelModelDownload`).
- **lib/types.ts** - TypeScript interfaces for Settings, HistoryEntry, Stats, Options, ModelInfo, DownloadProgress
- **pages/** - Popup (recording indicator), Onboarding (includes model download step), Dashboard
- **components/** - Feature components plus shadcn/ui components in `components/ui/`
  - `ModelDownloadProgress.tsx` - Download progress UI with progress bar, speed, ETA, and retry support
  - `ModelDownloadModal.tsx` - Dialog wrapper for model downloads triggered from settings
  - `ModelRecoveryModal.tsx` - Startup modal for missing model recovery

### Frontend-Backend Communication

The frontend uses `pyloid-js` RPC to call Python methods:
```typescript
import { rpc } from "pyloid-js";
const settings = await rpc.call("get_settings");
```

Backend sends events to popup window via:
```python
popup_window.invoke('popup-state', {'state': 'recording'})
```

### Recording Flow

1. User holds hotkey (configurable, default Ctrl+Win)
2. `HotkeyService.on_activate` -> `AppController._handle_hotkey_activate` -> `AudioService.start_recording`
3. Popup transitions to "recording" state, shows amplitude visualizer
4. User releases hotkey
5. `AudioService.stop_recording` returns audio numpy array
6. `TranscriptionService.transcribe` runs faster-whisper
7. `ClipboardService.paste_at_cursor` pastes text
8. History saved to database
9. Popup returns to "idle" state

### Qt Threading Pattern

The `keyboard` library runs hotkey callbacks in a separate thread, but Qt requires UI operations on the main thread. The solution uses Qt signals/slots:

1. `ThreadSafeSignals` class in `main.py` defines signals (recording_started, recording_stopped, etc.)
2. Callback functions from `AppController` emit signals instead of directly updating UI
3. Signals connect to slot functions with `Qt.QueuedConnection` to ensure they run on the main thread
4. Slot functions safely update popup state and window properties

### Popup Window Transparency

For transparent popup windows on Windows:
- Set `transparent=True` when creating the window
- Call `qwindow.setAttribute(Qt.WA_TranslucentBackground, True)` on the Qt window
- Set `webview.page().setBackgroundColor(QColor(0, 0, 0, 0))` before loading URL
- Re-apply `WA_TranslucentBackground` after any `setWindowFlags()` call

### Model Download Flow

1. App/Onboarding/Settings triggers model download via `startModelDownload(modelName)`
2. `ModelManager` creates daemon thread, starts `huggingface_hub.snapshot_download()`
3. Custom tqdm class captures progress, sends updates via callback (throttled to 10/sec)
4. Frontend receives `download-progress` events with percent, speed, ETA
5. User can cancel via `cancelModelDownload()` which sets CancelToken
6. On completion, model is cached in huggingface cache directory
7. Turbo model uses `mobiuslabsgmbh/faster-whisper-large-v3-turbo` (same as faster-whisper internal mapping)

## Key Patterns

- **Singleton controller**: `get_controller()` returns singleton `AppController` instance
- **UI callbacks**: Backend notifies frontend of state changes via callbacks set in `set_ui_callbacks()`
- **Thread-safe signals**: Qt signals with `QueuedConnection` marshal UI updates from background threads to main thread
- **Background threads**: Model loading, downloads, and transcription run in daemon threads
- **Domain logging**: All services use `get_logger(domain)` for structured logging with domains like `model`, `audio`, `hotkey`, etc.
- **Custom hotkeys**: Supports modifier-only combos (e.g., Ctrl+Win) and standard combos (e.g., Ctrl+R). Frontend captures keys, backend validates and registers.
- **Path alias**: Frontend uses `@/` for `src/` imports (configured in tsconfig.json and vite.config.ts)
- **Lazy pyautogui**: `ClipboardService` lazy-loads pyautogui via `_get_pyautogui()` to avoid `mouseinfo`'s `sys.exit()` when tkinter is missing in bundled builds
- **Reduced effects on Linux**: `App.tsx` adds `reduced-effects` class on Linux to disable `backdrop-filter`, animated orbs, and noise texture that cause sluggish UI under Qt WebEngine software rendering. Popup route is excluded (needs transparency).
- **Popup visibility**: `showPopup` setting controls the floating recording indicator. Backend uses `_popup_visible` flag and `on_popup_visibility_changed()` callback. When hidden, `resize_popup()` is skipped to prevent re-showing.

### Linux-Specific

- **evdev hotkeys**: Linux uses `evdev` for keyboard input instead of `keyboard` library (Wayland-compatible)
- **Wayland clipboard**: Uses `wl-copy` for clipboard, `wtype`/`dotool`/`ydotool` for paste keystroke, falls back to pyautogui via XWayland
- **Qt WebEngine flags**: `QTWEBENGINE_ENABLE_LINUX_ACCESSIBILITY=0` and Chromium flags (`--use-gl=egl`, `--disable-gpu-sandbox`) set in `main.py` to improve rendering performance
- **Hyprland rules**: `_setup_hyprland_window_rules()` in `main.py` configures popup as floating, pinned, no-focus via `hyprctl`
- **Multi-monitor**: `get_active_monitor_info()` re-detects cursor monitor on each recording start

## Testing

Python tests use pytest and are in `src-pyloid/tests/`. Test files include:
- `test_logger.py` - Logger infrastructure tests
- `test_model_manager.py` - Model download/cache management tests
- `test_transcription.py` - Transcription service tests (slow, downloads model on first run)
- `test_audio.py`, `test_hotkey.py`, `test_clipboard.py`, `test_settings.py`, `test_app_controller.py`

## UI Components

Uses shadcn/ui (New York style) with Tailwind CSS v4. Add components via:
```bash
npx shadcn@latest add <component>
```

## Git Commit Guidelines

- **Never add co-author lines** to commit messages
- Keep commit messages concise and descriptive
- Use conventional commit prefixes: `fix:`, `feat:`, `update:`, `refactor:`, etc.
- Follow the release guide at `docs/plans/release-guide.md` for creating releases
