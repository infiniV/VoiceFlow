export interface Settings {
  language: string;
  model: string;
  device: string;
  autoStart: boolean;
  retention: number;
  theme: "system" | "light" | "dark";
  onboardingComplete: boolean;
  microphone: number;
  saveAudioToHistory: boolean;
  // Hotkey settings
  holdHotkey: string;
  holdHotkeyEnabled: boolean;
  toggleHotkey: string;
  toggleHotkeyEnabled: boolean;
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
