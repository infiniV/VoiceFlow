# VoiceFlow — Domain Glossary

The shared language for VoiceFlow. Terms here are the canonical names used in code,
DB schemas, RPC methods, logs, and tests. UI strings may diverge (see "Display label"
where it does).

## Recording

A captured audio file plus its optional transcript and optional AI-generated summary.
The unit of work for the meeting-notes feature.

A Recording is created in one of two ways:
1. **Live capture** — user starts the recorder in the app, audio is streamed to disk from
   one or more sources (mic, system-audio loopback), then stopped.
2. **Import** — user picks an existing audio file from disk; it is copied into VoiceFlow's
   recordings directory and treated as if it had been live-captured.

A Recording is the entity in the DB (`recordings` table), in RPC methods (`recordings_*`),
in services (`RecordingService`, `RecordingsRepository`), in the audio folder
(`~/.VoiceFlow/recordings/`), and in logs (`domain=recording`).

**Display label**: the UI surfaces this feature as "Meetings" (the dashboard nav item, page
titles, button copy) because the dominant use case is multi-party meeting capture. A
Recording is shown to the user as a "meeting" in the interface, but it is a `recording`
everywhere else. This split is intentional — see `docs/adr/0002-recording-vs-meeting-naming.md`.

Distinct from **History** (one-shot push-to-talk dictations, `history` table) — Recordings
are long-form (minutes to hours), have a structured lifecycle (recording → transcribing →
summarizing), and live in their own table.
