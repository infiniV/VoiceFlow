<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="media/logo-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="media/logo-light.png">
    <img src="media/logo-dark.png" alt="Dictore" width="320">
  </picture>
</h1>

<p align="center">
  Hold a hotkey. Speak. Release. The transcript pastes itself at your cursor.
</p>

<p align="center">
  <img src="media/dashboard.png" alt="Dictore dashboard" width="100%">
</p>

<p align="center">
  Local Whisper dictation for Windows and Linux. No account, no cloud, no monthly bill.
  <br/>
  <sub>macOS builds and runs but isn't officially supported yet.</sub>
</p>

<p align="center">
  <a href="https://github.com/infiniV/Dictore/releases/tag/v1.6.0"><img src="https://img.shields.io/badge/Download-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Download for Windows"></a>
  <a href="https://github.com/infiniV/Dictore/releases/tag/v1.6.0"><img src="https://img.shields.io/badge/Download-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Download for Linux"></a>
  <a href="https://get-voice-flow.vercel.app/"><img src="https://img.shields.io/badge/Website-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Website"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License"></a>
</p>

<p align="center">
  <sub>Latest: <a href="https://github.com/infiniV/Dictore/releases/tag/v1.6.0"><code>v1.6.0</code></a> · <a href="https://github.com/infiniV/Dictore/releases">all releases</a></sub>
</p>

<p align="center">
  <b>New in v1.6.0 — <a href="#meetings">Meetings</a>:</b> long-form recording with mic + system audio, local transcription, and bring-your-own-LLM summaries.
</p>

---

## What it does

Dictore lives in your system tray. Hold a global hotkey, a small popup pops up with a live amplitude meter, you talk, you release, and the transcript is typed at the cursor. That's it.

The inference runs on your machine through [faster-whisper](https://github.com/SYSTRAN/faster-whisper). CUDA when you have it, CPU when you don't. The audio never touches a network socket.

<h2 id="meetings">Meetings <sub><sup>new in v1.6.0</sup></sub></h2>

Long-form recording that captures your mic plus system audio (Zoom, Meet, anything that plays through your speakers) into one stereo file, transcribes it locally with Whisper, and runs the summary through an LLM provider you choose.

<p align="center">
  <img src="media/meetings-detail.png" alt="Meeting detail with transcript, summary, and audio player" width="100%">
</p>

- **System audio + mic in one file.** Stereo capture via WASAPI loopback (Windows) and PipeWire/PulseAudio (Linux).
- **Pause, resume, stop** from the dashboard or the tray menu — recording survives across hour-long calls.
- **Re-transcribe** any saved recording with a different model, device, or language without re-recording.
- **Bring your own LLM.** OpenAI, Groq, OpenRouter, Ollama, or any OpenAI-compatible endpoint. Keys live in your OS keychain.
- **Auto-rename** from a default timestamp to a real topic once the transcript lands.
- **Export** to Markdown, plain text, SRT, or structured JSON.
- **Built-in playback** via the `dictore://` URL scheme — jump straight from any transcript line into the audio.

Recording, transcription, search, and storage stay local. The only network call is the optional summary request — skip it, point it at a local Ollama, or send it to a provider you already pay for.

## Features

- **Fully local.** Audio stays in RAM. No telemetry, no analytics, no phone-home.
- **16+ Whisper models.** Tiny (75 MB) through Large-v3 (3 GB), plus Turbo, distilled, and `.en` variants. The picker shows speed, accuracy, parameter count, and disk size for each.
- **CUDA when available.** Auto-detects your GPU, falls back to CPU.
- **Hold or Toggle modes.** Configurable hotkeys including modifier-only combos like `Ctrl+Win`.
- **Wayland and X11.** Native `evdev` input on Linux, Hyprland window rules, `wl-copy` and `wtype`/`ydotool` for paste.
- **99+ languages.** Whisper handles language detection automatically.
- **Searchable history.** SQLite log of every transcript, stored at `~/.Dictore/`.
- **Dark mode by default.** Light and system themes if you want them.

## Dictore vs cloud dictation

|  | Dictore | Cloud services |
| :--- | :--- | :--- |
| Cost | $0 | ~$10–15/month |
| Where audio goes | Your RAM | Their servers |
| Works offline | Yes | No |
| Account required | No | Yes |
| License | MIT | Closed |

## Install

Grab the latest binary from [Releases](https://github.com/infiniV/Dictore/releases) — currently [`v1.6.0`](https://github.com/infiniV/Dictore/releases/tag/v1.6.0):

- **Windows 10/11**: `.exe` installer (Inno Setup)
- **Linux**: `.AppImage` or `.tar.gz`

64-bit only. First launch walks you through a seven-step setup: microphone, compute device, Whisper model download, hotkey. If you delete the model later, a recovery dialog lets you re-download or pick a different one.

## Build from source

```bash
git clone https://github.com/infiniV/Dictore.git
cd Dictore
pnpm run setup        # installs Node and Python deps
pnpm run dev          # Vite frontend + Pyloid backend
```

Platform installers (run on the matching OS):

```bash
pnpm run build:installer          # Windows (.exe via Inno Setup)
pnpm run build:installer:linux    # Linux (.AppImage and .tar.gz)
pnpm run build:installer:macos    # macOS (.dmg, unsupported)
```

## Stack

| Layer | Tech |
| :--- | :--- |
| Shell | [Pyloid](https://github.com/pyloid/pyloid) (PySide6 + Qt WebEngine) |
| Inference | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2) |
| Frontend | React 18, Vite, Tailwind v4, shadcn/ui |
| Storage | SQLite at `~/.Dictore/Dictore.db` |

## License

MIT. See [LICENSE](LICENSE).

[Releases](https://github.com/infiniV/Dictore/releases) · [Issues](https://github.com/infiniV/Dictore/issues) · [Website](https://get-voice-flow.vercel.app/)
