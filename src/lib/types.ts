export interface Settings {
  language: string;
  model: string;
  device: string;
  autoStart: boolean;
  retention: number;
  theme: "midnight" | "aurora" | "ember" | "ocean" | "snowfall" | "neonCity";
  autoRewriteEnabled: boolean;
  rewritePreset: "grammar_correct" | "professional" | "casual_spoken" | "concise";
  fillerRemovalEnabled: boolean;
  onboardingComplete: boolean;
  microphone: number;
  saveAudioToHistory: boolean;
  // UI settings
  showPopup: boolean;
  // Hotkey settings
  holdHotkey: string;
  holdHotkeyEnabled: boolean;
  toggleHotkey: string;
  toggleHotkeyEnabled: boolean;
  // Transcription settings
  prependSpace: boolean;
  // Recordings (Meetings) — backend-persisted toggles for the long-form flow.
  recordingsAutoRenameTitle?: boolean;
}

export interface HistoryEntry {
  id: number;
  text: string;
  char_count: number;
  word_count: number;
  created_at: string;
  has_audio?: boolean;
  audio_relpath?: string | null;
  audio_duration_ms?: number | null;
  audio_size_bytes?: number | null;
  audio_mime?: string | null;
}

export interface Stats {
  totalTranscriptions: number;
  totalWords: number;
  totalCharacters: number;
  streakDays: number;
}

export interface Microphone {
  id: number;
  name: string;
  channels: number;
}

export interface Options {
  models: string[];
  languages: string[];
  retentionOptions: Record<string, number>;
  themeOptions: string[];
  microphones: Microphone[];
  deviceOptions: string[];
}

export interface ModelInfo {
  name: string;
  sizeBytes: number;
  cached: boolean;
}

export interface DownloadProgress {
  model: string;
  percent: number;
  downloadedBytes: number;
  totalBytes: number;
  speedBps: number;
  etaSeconds: number;
}

export interface DownloadComplete {
  model: string;
  success: boolean;
  cancelled?: boolean;
  alreadyCached?: boolean;
  error?: string;
}

export interface HotkeyValidation {
  valid: boolean;
  error: string | null;
  conflicts: boolean;
  normalized: string;
}

export interface GpuInfo {
  cudaAvailable: boolean;
  deviceCount: number;
  gpuName: string | null;
  supportedComputeTypes: string[];
  currentDevice: string;
  currentComputeType: string;
  cudnnAvailable: boolean;
  cudnnMessage: string | null;
}

export interface DeviceValidation {
  valid: boolean;
  error: string | null;
}

export interface CudnnDownloadInfo {
  hasNvidiaGpu: boolean;
  cudnnInstalled: boolean;
  downloadSizeMb: number;
}

export interface CudnnDownloadResult {
  success: boolean;
  error?: string | null;
  started?: boolean;
  alreadyRunning?: boolean;
}

export interface CudnnDownloadProgress {
  downloading: boolean;
  downloadedBytes: number;
  totalBytes: number;
  percent: number;
  error: string | null;
  complete: boolean;
  success: boolean;
  status: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Recordings (Meetings feature)
// Backed by services/recording/* — see the approved plan and ADR-0001 for
// channel layout and the Q5/Q7/Q8 decisions.

export type RecordingSource = "mic" | "loopback";

export type RecorderStateName = "idle" | "recording" | "paused" | "stopping";

export type TranscriptStatus =
  | "pending"
  | "transcribing"
  | "done"
  | "error"
  | "cancelled";

export type SummaryStatus = "idle" | "summarizing" | "done" | "error";

export interface AudioSource {
  id: number;
  name: string;
  kind: RecordingSource;
  hostApi: string;
  isDefault: boolean;
}

export interface AudioSourceList {
  mic: AudioSource[];
  loopback: AudioSource[];
}

export interface RecorderState {
  state: RecorderStateName;
  recordingId: number | null;
  durationMs: number;
  micPeakDb: number | null;
  loopbackPeakDb: number | null;
}

export interface Recording {
  id: number;
  title: string;
  audioRelpath: string | null;
  audioDurationMs: number | null;
  audioSizeBytes: number | null;
  audioSampleRate: number | null;
  audioChannels: number | null;
  sources: RecordingSource[];
  language: string | null;
  transcript: string | null;
  transcriptModel: string | null;
  transcriptStatus: TranscriptStatus;
  transcriptProgress: number;
  transcriptError: string | null;
  summary: string | null;
  summaryProvider: string | null;
  summaryStatus: SummaryStatus;
  summaryProgress: number;
  summaryError: string | null;
  tags: string[];
  notes: string | null;
  recorderState: RecorderStateName | null;
  createdAt: string;
  updatedAt: string;
}

export interface RecordingSegment {
  id: number;
  recordingId: number;
  startMs: number;
  endMs: number;
  text: string;
}

export interface RecordingWithSegments extends Recording {
  segments: RecordingSegment[];
}

export type LLMPreset = "openai" | "groq" | "openrouter" | "ollama" | "custom";

export interface LLMConfig {
  preset: LLMPreset;
  endpoint: string;
  model: string;
  hasApiKey: boolean;
  promptTemplate: string;
}

export interface LLMTestResult {
  ok: boolean;
  error: string | null;
  models?: string[];
}

export interface RecordingTranscribeProgress {
  recordingId: number;
  progress: number;
  currentText?: string;
}

export interface RecordingSummarizeProgress {
  recordingId: number;
  progress: number;
  partialText?: string;
}

export interface RecordingJobComplete {
  recordingId: number;
  success: boolean;
  error?: string;
}

export interface CachedModel {
  name: string;
  cached: boolean;
}
