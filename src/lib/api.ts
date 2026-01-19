import { rpc } from "pyloid-js";
import type { Settings, HistoryEntry, Options, Stats, ModelInfo, HotkeyValidation, GpuInfo, DeviceValidation, CudnnDownloadInfo, CudnnDownloadResult, CudnnDownloadProgress, PlatformInfo } from "./types";

export const api = {
  async getSettings(): Promise<Settings> {
    return rpc.call("get_settings");
  },

  async getStats(): Promise<Stats> {
    return rpc.call("get_stats");
  },

  async updateSettings(settings: Partial<Settings>): Promise<Settings> {
    return rpc.call("update_settings", settings);
  },

  async getOptions(): Promise<Options> {
    return rpc.call("get_options");
  },

  async getHistory(
    limit = 100,
    offset = 0,
    search?: string,
    include_audio_meta?: boolean
  ): Promise<HistoryEntry[]> {
    return rpc.call("get_history", { limit, offset, search, include_audio_meta });
  },

  async getHistoryAudio(historyId: number): Promise<{ base64: string; mime: string; fileName?: string; sizeBytes?: number; durationMs?: number }> {
    return rpc.call("get_history_audio", { history_id: historyId });
  },

  async deleteHistory(historyId: number): Promise<void> {
    await rpc.call("delete_history", { history_id: historyId });
  },

  async copyToClipboard(text: string): Promise<void> {
    await rpc.call("copy_to_clipboard", { text });
  },

  async stopRecording(): Promise<void> {
    await rpc.call("stop_recording");
  },

  async startTestRecording(): Promise<void> {
    await rpc.call("start_test_recording");
  },

  async stopTestRecording(): Promise<{ success: boolean; transcript: string; error?: string }> {
    return rpc.call("stop_test_recording");
  },

  async openDataFolder(): Promise<void> {
    await rpc.call("open_data_folder");
  },

  async openExternalUrl(url: string): Promise<void> {
    await rpc.call("open_external_url", { url });
  },

  async setPopupEnabled(enabled: boolean): Promise<void> {
    await rpc.call("set_popup_enabled", { enabled });
  },

  async resetAllData(): Promise<void> {
    await rpc.call("reset_all_data");
  },

  async windowMinimize(): Promise<void> {
    await rpc.call("window_minimize");
  },

  async windowToggleMaximize(): Promise<void> {
    await rpc.call("window_toggle_maximize");
  },

  async windowClose(): Promise<void> {
    await rpc.call("window_close");
  },

  // Model Management
  async getModelInfo(modelName: string): Promise<ModelInfo> {
    return rpc.call("get_model_info", { model_name: modelName });
  },

  async startModelDownload(modelName: string): Promise<{ success: boolean; alreadyCached?: boolean; started?: boolean }> {
    return rpc.call("start_model_download", { model_name: modelName });
  },

  async cancelModelDownload(): Promise<{ success: boolean; cancelled: boolean }> {
    return rpc.call("cancel_model_download");
  },

  async clearModelCache(): Promise<{ success: boolean; deleted_bytes: number; deleted_models: string[]; error: string | null }> {
    return rpc.call("clear_model_cache");
  },

  // Hotkey validation
  async validateHotkey(
    hotkey: string,
    excludeCurrent?: "holdHotkey" | "toggleHotkey"
  ): Promise<HotkeyValidation> {
    return rpc.call("validate_hotkey", { hotkey, excludeCurrent });
  },

  // GPU/Device info
  async getGpuInfo(): Promise<GpuInfo> {
    return rpc.call("get_gpu_info");
  },

  async validateDevice(device: string): Promise<DeviceValidation> {
    return rpc.call("validate_device", { device });
  },

  // cuDNN download
  async getCudnnDownloadInfo(): Promise<CudnnDownloadInfo> {
    return rpc.call("get_cudnn_download_info");
  },

  async downloadCudnn(): Promise<CudnnDownloadResult> {
    return rpc.call("download_cudnn");
  },

  async getCudnnDownloadProgress(): Promise<CudnnDownloadProgress> {
    return rpc.call("get_cudnn_download_progress");
  },

  async clearCudaLibs(): Promise<{ success: boolean }> {
    return rpc.call("clear_cuda_libs");
  },

  // Platform info (Linux support)
  async getPlatformInfo(): Promise<PlatformInfo> {
    return rpc.call("get_platform_info");
  },

  async getSignalCommand(): Promise<{ command: string }> {
    return rpc.call("get_signal_command");
  },
};
