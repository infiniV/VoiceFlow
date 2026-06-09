import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ArrowLeft,
  Check,
  Mic,
  AlertCircle,
  Zap,
  Cpu,
  Keyboard,
  Download,
  HardDrive,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { AudioVisualizer } from "@/components/AudioVisualizer";
import { ModelDownloadProgress } from "@/components/ModelDownloadProgress";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Settings, Options, GpuInfo } from "@/lib/types";
import {
  MODEL_OPTIONS,
  MODEL_CATEGORIES,
  ONBOARDING_FEATURES,
  isEnglishOnlyModel,
} from "@/lib/constants";
import { applyThemePalette, THEME_PALETTES } from "@/lib/themes";

// ============================================================================
// STEP: WELCOME
// ============================================================================

const StepWelcome = () => (
  <div className="space-y-8 max-w-2xl w-full">
    <p className="text-base md:text-lg leading-relaxed text-cream-muted text-center">
      Dictation designed for{" "}
      <span className="text-accent-500 font-medium">privacy</span> and{" "}
      <span className="text-accent-500 font-medium">flow</span>.
    </p>

    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {ONBOARDING_FEATURES.map((feature) => (
        <div
          key={feature.label}
          className="border border-border rounded-md bg-surface flex items-start gap-3 p-4 text-left"
        >
          <feature.icon
            className="w-4 h-4 mt-0.5 flex-shrink-0 text-accent-500"
            strokeWidth={2}
          />
          <div className="min-w-0">
            <p className="font-medium text-cream text-sm leading-tight">
              {feature.label}
            </p>
            <p className="text-[11px] text-cream-muted leading-relaxed mt-1">
              {feature.desc}
            </p>
          </div>
        </div>
      ))}
    </div>
  </div>
);

// ============================================================================
// STEP: AUDIO
// ============================================================================

const StepAudio = ({
  microphone,
  setMicrophone,
  options,
}: {
  microphone: number;
  setMicrophone: (id: number) => void;
  options: Options;
}) => {
  const [amplitude, setAmplitude] = useState(0);
  const [isListening, setIsListening] = useState(false);

  useEffect(() => {
    const handleAmplitude = (e: CustomEvent<number>) => {
      setAmplitude(e.detail);
    };
    document.addEventListener("amplitude", handleAmplitude as EventListener);
    return () => {
      document.removeEventListener(
        "amplitude",
        handleAmplitude as EventListener
      );
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    const startRecording = async () => {
      try {
        await api.updateSettings({ microphone });
        await api.startTestRecording();
        if (mounted) setIsListening(true);
      } catch (error) {
        console.error("[Audio] Failed to start test recording:", error);
      }
    };
    const timer = setTimeout(startRecording, 100);
    return () => {
      mounted = false;
      clearTimeout(timer);
      api.stopTestRecording().catch(() => {});
      setIsListening(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDeviceChange = async (backendDeviceId: string) => {
    const backendId = Number(backendDeviceId);
    setMicrophone(backendId);
    try {
      await api.stopTestRecording();
    } catch {
      // ignore
    }
    try {
      await api.updateSettings({ microphone: backendId });
      await api.startTestRecording();
      setIsListening(true);
    } catch (error) {
      console.error("[Audio] Failed to restart recording:", error);
    }
  };

  return (
    <div className="space-y-5 max-w-xl w-full">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 mb-2">
          input device
        </p>
        <Select value={String(microphone)} onValueChange={handleDeviceChange}>
          <SelectTrigger className="h-12 text-sm bg-secondary/40 border-border hover:bg-secondary/60 transition-colors rounded-md">
            <div className="flex items-center gap-2">
              <Mic className="w-4 h-4 text-cream-muted/70" strokeWidth={2} />
              <SelectValue placeholder="Select a microphone" />
            </div>
          </SelectTrigger>
          <SelectContent>
            {options.microphones.map((mic) => (
              <SelectItem key={mic.id} value={String(mic.id)}>
                {mic.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 mb-2 flex items-center justify-between">
          <span>level meter</span>
          <span
            className={cn(
              "flex items-center gap-1.5 normal-case tracking-normal text-[11px]",
              isListening ? "text-accent-500" : "text-cream-muted/40"
            )}
          >
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full",
                isListening ? "bg-accent-500" : "bg-cream-muted/30"
              )}
            />
            {isListening ? "listening" : "idle"}
          </span>
        </p>
        <div className="h-24 w-full border border-border rounded-md bg-surface flex items-center justify-center px-4">
          {isListening ? (
            <AudioVisualizer
              amplitude={amplitude}
              bars={40}
              className="gap-1 h-14 text-accent-500"
            />
          ) : (
            <span className="font-mono text-xs text-cream-muted/60">
              waiting for microphone…
            </span>
          )}
        </div>
      </div>

      <p className="text-sm text-cream-muted leading-relaxed">
        Speak now to test your input levels — the meter should respond to your
        voice.
      </p>
    </div>
  );
};

// ============================================================================
// STEP: HARDWARE
// ============================================================================

const DEVICE_OPTIONS = [
  {
    id: "auto",
    label: "Auto",
    desc: "Recommended",
    detail: "Best available",
    description:
      "Automatically selects the best available compute device. Uses GPU if available and properly configured, otherwise falls back to CPU.",
    icon: Zap,
    bestFor:
      "Most users who want optimal performance without manual configuration.",
  },
  {
    id: "cuda",
    label: "CUDA GPU",
    desc: "NVIDIA only",
    detail: "Fastest",
    description:
      "Uses NVIDIA GPU with CUDA acceleration for maximum transcription speed. Requires compatible NVIDIA GPU with CUDA libraries (cuDNN + cuBLAS).",
    icon: Cpu,
    bestFor:
      "Users with NVIDIA GPUs who want the fastest possible transcription.",
  },
  {
    id: "cpu",
    label: "CPU only",
    desc: "Universal",
    detail: "Compatible",
    description:
      "Uses CPU for transcription. Works on any system but slower than GPU acceleration. Good fallback option.",
    icon: Cpu,
    bestFor:
      "Systems without compatible GPU or when GPU acceleration causes issues.",
  },
];

const StepHardware = ({
  device,
  setDevice,
  gpuInfo,
  onGpuInfoUpdate,
}: {
  device: string;
  setDevice: (d: string) => void;
  gpuInfo: GpuInfo | null;
  onGpuInfoUpdate: () => void;
}) => {
  const [deviceError, setDeviceError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<{
    percent: number;
    downloadedBytes: number;
    totalBytes: number;
  } | null>(null);

  useEffect(() => {
    if (!downloading) {
      setDownloadProgress(null);
      return;
    }
    const pollProgress = async () => {
      try {
        const progress = await api.getCudnnDownloadProgress();
        if (progress.downloading) {
          setDownloadProgress({
            percent: progress.percent,
            downloadedBytes: progress.downloadedBytes,
            totalBytes: progress.totalBytes,
          });
        } else if (progress.complete) {
          setDownloading(false);
          if (progress.success) onGpuInfoUpdate();
          else if (progress.error) setDownloadError(progress.error);
        }
      } catch (err) {
        console.error("Failed to poll progress:", err);
      }
    };
    const interval = setInterval(pollProgress, 500);
    pollProgress();
    return () => clearInterval(interval);
  }, [downloading, onGpuInfoUpdate]);

  const handleDeviceSelect = async (newDevice: string) => {
    setDeviceError(null);
    const validation = await api.validateDevice(newDevice);
    if (!validation.valid) {
      setDeviceError(validation.error);
      return;
    }
    setDevice(newDevice);
  };

  const handleDownloadCudnn = async () => {
    setDownloading(true);
    setDownloadError(null);
    setDownloadProgress(null);
    try {
      const result = await api.downloadCudnn();
      if (!result.success) {
        setDownloadError(result.error || "Failed to start download");
        setDownloading(false);
      }
    } catch {
      setDownloadError("Download failed. Check your internet connection.");
      setDownloading(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const showDownloadButton = gpuInfo?.gpuName && !gpuInfo?.cudnnAvailable;
  const resolvedDevice =
    device === "auto"
      ? gpuInfo?.cudaAvailable
        ? "cuda"
        : "cpu"
      : device;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6 w-full max-w-5xl h-full min-h-0">
      <div className="space-y-4 min-w-0 overflow-y-auto pr-2">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
            compute device
          </p>
          <p className="font-mono text-[10px] flex items-center gap-2">
            <span className="text-cream-muted/40 uppercase tracking-widest">
              resolves to
            </span>
            <span
              className={cn(
                resolvedDevice === "cuda"
                  ? "text-accent-500"
                  : "text-cream-muted",
                "uppercase tracking-widest"
              )}
            >
              {resolvedDevice}
            </span>
          </p>
        </div>

        <div
          className="grid grid-cols-3 gap-2"
          role="radiogroup"
          aria-label="Select compute device"
        >
          {DEVICE_OPTIONS.map((d) => {
            const isActive = device === d.id;
            const isDisabled = d.id === "cuda" && !gpuInfo?.cudaAvailable;
            return (
              <button
                key={d.id}
                type="button"
                role="radio"
                aria-checked={isActive}
                disabled={isDisabled}
                className={cn(
                  "relative p-4 rounded-md text-left transition-colors flex flex-col gap-2 border",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40 focus-visible:ring-offset-1",
                  isActive
                    ? "bg-accent-500/[0.06] border-accent-500/40"
                    : isDisabled
                      ? "border-border bg-secondary/20 opacity-50 cursor-not-allowed"
                      : "border-border bg-secondary/30 hover:bg-secondary/60"
                )}
                onClick={() => !isDisabled && handleDeviceSelect(d.id)}
              >
                <div className="flex items-center justify-between w-full">
                  <span
                    className={cn(
                      "font-display text-sm font-medium tracking-tight",
                      isActive ? "text-cream" : "text-cream"
                    )}
                  >
                    {d.label}
                  </span>
                  {isActive && (
                    <span
                      className="w-1.5 h-1.5 rounded-full bg-accent-500 flex-shrink-0"
                      aria-hidden="true"
                    />
                  )}
                </div>
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-cream-muted/60">
                  {d.desc}
                </span>
                {isDisabled && (
                  <span className="font-mono text-[10px] uppercase tracking-widest text-amber-500/80 mt-auto">
                    unavailable
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {deviceError && (
          <p className="font-mono text-[11px] text-destructive flex items-center gap-2 border-l-2 border-destructive/40 pl-3 py-1">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={2} />
            {deviceError}
          </p>
        )}

        {showDownloadButton && (
          <div className="border border-amber-500/30 bg-amber-500/[0.03] rounded-md p-4 space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber-500/90">
                gpu acceleration available
              </p>
            </div>
            <p className="text-xs text-cream-muted leading-relaxed">
              Download NVIDIA CUDA libraries (cuDNN + cuBLAS) to enable GPU
              acceleration.
            </p>
            <button
              type="button"
              onClick={handleDownloadCudnn}
              disabled={downloading}
              className="w-full flex items-center justify-center gap-2 h-10 rounded-md bg-accent-500 text-zinc-950 hover:bg-accent-600 transition-colors text-sm font-medium disabled:opacity-50"
            >
              {downloading ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                  {downloadProgress
                    ? `downloading… ${downloadProgress.percent}%`
                    : "starting…"}
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" strokeWidth={2.5} />
                  Download CUDA libraries (~880 MB)
                </>
              )}
            </button>
            {downloading && downloadProgress && (
              <div className="space-y-1.5">
                <div className="h-1 w-full bg-secondary/50 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent-500 transition-[width] duration-300 ease-out"
                    style={{ width: `${downloadProgress.percent}%` }}
                  />
                </div>
                <p className="font-mono text-[10px] text-cream-muted/70 text-center">
                  {formatBytes(downloadProgress.downloadedBytes)} /{" "}
                  {formatBytes(downloadProgress.totalBytes)}
                </p>
              </div>
            )}
            {downloadError && (
              <p className="font-mono text-[11px] text-destructive">
                {downloadError}
              </p>
            )}
          </div>
        )}
      </div>

      <HardwareDetailsPanel device={device} gpuInfo={gpuInfo} />
    </div>
  );
};

function HardwareDetailsPanel({
  device,
  gpuInfo,
}: {
  device: string;
  gpuInfo: GpuInfo | null;
}) {
  const selected = DEVICE_OPTIONS.find((d) => d.id === device);
  const status = gpuInfo?.cudaAvailable
    ? { label: "ready", tone: "accent" as const }
    : gpuInfo?.gpuName && !gpuInfo?.cudnnAvailable
      ? { label: "setup needed", tone: "amber" as const }
      : { label: "cpu mode", tone: "muted" as const };

  return (
    <div className="border border-border rounded-md bg-surface p-5 space-y-5 h-full overflow-y-auto min-h-0">
      {selected && (
        <>
          <div className="space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
              selection
            </p>
            <h3 className="font-display text-lg font-medium text-cream tracking-tight leading-tight">
              {selected.label}
            </h3>
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cream-muted/60">
              {selected.detail}
            </p>
          </div>

          <div className="space-y-1.5 pt-4 border-t border-border">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
              best for
            </p>
            <p className="text-xs text-cream-muted leading-relaxed">
              {selected.bestFor}
            </p>
          </div>

          <div className="space-y-1.5">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
              about
            </p>
            <p className="text-[11px] text-cream-muted leading-relaxed">
              {selected.description}
            </p>
          </div>
        </>
      )}

      <div className="space-y-3 pt-4 border-t border-border">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
            hardware
          </p>
          <span
            className={cn(
              "font-mono text-[10px] uppercase tracking-widest",
              status.tone === "accent" && "text-accent-500",
              status.tone === "amber" && "text-amber-500",
              status.tone === "muted" && "text-cream-muted/60"
            )}
          >
            {status.label}
          </span>
        </div>

        <dl className="font-mono text-[11px] grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
          {gpuInfo?.gpuName && (
            <>
              <dt className="text-cream-muted/60 uppercase tracking-widest text-[9px] self-center">
                gpu
              </dt>
              <dd className="text-cream truncate" title={gpuInfo.gpuName}>
                {gpuInfo.gpuName}
              </dd>
              <dt className="text-cream-muted/60 uppercase tracking-widest text-[9px] self-center">
                cuda
              </dt>
              <dd
                className={
                  gpuInfo.cudaAvailable ? "text-accent-500" : "text-cream-muted"
                }
              >
                {gpuInfo.cudaAvailable ? "available" : "unavailable"}
              </dd>
              <dt className="text-cream-muted/60 uppercase tracking-widest text-[9px] self-center">
                cudnn
              </dt>
              <dd
                className={
                  gpuInfo.cudnnAvailable ? "text-accent-500" : "text-amber-500"
                }
              >
                {gpuInfo.cudnnAvailable ? "installed" : "missing"}
              </dd>
            </>
          )}
          {!gpuInfo?.gpuName && (
            <>
              <dt className="text-cream-muted/60 uppercase tracking-widest text-[9px] self-center">
                device
              </dt>
              <dd className="text-cream">cpu only</dd>
            </>
          )}
        </dl>

        {gpuInfo?.supportedComputeTypes &&
          gpuInfo.supportedComputeTypes.length > 0 && (
            <div className="space-y-1.5">
              <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
                compute types
              </p>
              <div className="flex flex-wrap gap-1">
                {gpuInfo.supportedComputeTypes.map((ct) => (
                  <span
                    key={ct}
                    className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-secondary/50 text-cream-muted"
                  >
                    {ct}
                  </span>
                ))}
              </div>
            </div>
          )}

        <p className="text-[11px] text-cream-muted/70 leading-relaxed pt-1">
          {gpuInfo?.cudaAvailable
            ? "Your system is fully configured for GPU acceleration."
            : gpuInfo?.gpuName && !gpuInfo?.cudnnAvailable
              ? "Download CUDA libraries from the left to enable GPU acceleration."
              : "No compatible NVIDIA GPU detected. CPU transcription works well — just slower."}
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// STEP: MODEL
// ============================================================================

const RatingBar = ({
  value,
  max = 5,
  label,
}: {
  value: number;
  max?: number;
  label: string;
}) => (
  <div className="flex items-center gap-3">
    <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-cream-muted/60 w-16 flex-shrink-0">
      {label}
    </span>
    <div className="flex gap-0.5 flex-1">
      {Array.from({ length: max }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "h-1 flex-1 rounded-full",
            i < value ? "bg-accent-500" : "bg-cream-muted/15"
          )}
        />
      ))}
    </div>
  </div>
);

const StepModel = ({
  language,
  setLanguage,
  model,
  setModel,
  options,
  device,
  gpuInfo,
}: {
  language: string;
  setLanguage: (l: string) => void;
  model: string;
  setModel: (m: string) => void;
  options: Options;
  device: string;
  gpuInfo: GpuInfo | null;
}) => {
  const selectedModel = MODEL_OPTIONS.find((m) => m.id === model);
  const categoryInfo = selectedModel
    ? MODEL_CATEGORIES[selectedModel.category]
    : null;
  const resolvedDevice =
    device === "auto" ? (gpuInfo?.cudaAvailable ? "cuda" : "cpu") : device;

  const handleModelSelect = (modelId: string) => {
    setModel(modelId);
    if (isEnglishOnlyModel(modelId) && language !== "en") setLanguage("en");
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6 w-full max-w-6xl h-full min-h-0">
      <div className="space-y-5 min-w-0 overflow-y-auto pr-2">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 mb-2">
            language
          </p>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="h-10 bg-secondary/40 border-border hover:bg-secondary/60 transition-colors rounded-md max-w-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="max-h-[280px]">
              {options.languages.map((lang) => (
                <SelectItem key={lang} value={lang}>
                  {lang === "auto" ? "Auto-detect" : lang.toUpperCase()}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
              model
            </p>
            <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-widest">
              <span
                className={
                  resolvedDevice === "cuda"
                    ? "text-accent-500"
                    : "text-cream-muted/60"
                }
              >
                {resolvedDevice}
              </span>
              <span className="text-cream-muted/30">·</span>
              <span className="text-accent-500/80">local only</span>
            </div>
          </div>

          <div
            className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2"
            role="radiogroup"
            aria-label="Select processing model"
          >
            {MODEL_OPTIONS.map((m) => {
              const isActive = model === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  className={cn(
                    "relative p-3 rounded-md text-left transition-colors flex flex-col gap-1 border",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40 focus-visible:ring-offset-1",
                    isActive
                      ? "bg-accent-500/[0.06] border-accent-500/40"
                      : "border-border bg-secondary/30 hover:bg-secondary/60"
                  )}
                  onClick={() => handleModelSelect(m.id)}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="font-display text-sm font-medium tracking-tight text-cream">
                      {m.label}
                    </span>
                    {isActive && (
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-accent-500 flex-shrink-0"
                        aria-hidden="true"
                      />
                    )}
                  </div>
                  <span className="font-mono text-[10px] text-cream-muted/70">
                    {m.detail}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {selectedModel && (
        <div className="border border-border rounded-md bg-surface p-5 space-y-5 h-full overflow-y-auto min-h-0">
          <div className="space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 flex items-center justify-between">
              <span>model</span>
              {categoryInfo && (
                <span
                  className={cn(
                    "normal-case tracking-normal text-[11px]",
                    categoryInfo.color
                  )}
                >
                  {categoryInfo.label}
                </span>
              )}
            </p>
            <h3 className="font-display text-lg font-medium text-cream tracking-tight leading-tight">
              {selectedModel.label}
            </h3>
            <p className="text-xs text-cream-muted leading-relaxed">
              {selectedModel.desc}
            </p>
          </div>

          <div className="space-y-2 pt-4 border-t border-border">
            <RatingBar value={selectedModel.speed} label="speed" />
            <RatingBar value={selectedModel.accuracy} label="accuracy" />
          </div>

          <dl className="font-mono text-[11px] grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 pt-4 border-t border-border">
            <dt className="text-cream-muted/60 uppercase tracking-widest text-[9px] self-center">
              detail
            </dt>
            <dd className="text-cream">{selectedModel.detail}</dd>
            <dt className="text-cream-muted/60 uppercase tracking-widest text-[9px] self-center">
              size
            </dt>
            <dd className="text-cream">{selectedModel.size}</dd>
          </dl>

          <div className="space-y-1.5 pt-4 border-t border-border">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
              best for
            </p>
            <p className="text-xs text-cream-muted leading-relaxed">
              {selectedModel.bestFor}
            </p>
          </div>

          <div className="space-y-1.5">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
              about
            </p>
            <p className="text-[11px] text-cream-muted leading-relaxed">
              {selectedModel.description}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// STEP: THEME
// ============================================================================

const StepTheme = ({
  theme,
  setTheme,
  autoStart,
  setAutoStart,
}: {
  theme: Settings["theme"];
  setTheme: (t: Settings["theme"]) => void;
  autoStart: boolean;
  setAutoStart: (b: boolean) => void;
}) => (
  <div className="space-y-8 max-w-md w-full">
    <fieldset className="space-y-3">
      <legend className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
        interface theme
      </legend>
      <div
        className="grid grid-cols-2 sm:grid-cols-3 gap-3"
        role="radiogroup"
        aria-label="Theme selection"
      >
        {THEME_PALETTES.map((palette) => {
          const isActive = theme === palette.id;
          return (
            <button
              key={palette.id}
              type="button"
              role="radio"
              aria-checked={isActive}
              className={cn(
                "relative p-4 rounded-xl flex flex-col items-start gap-3 transition-all border text-left",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500/40 focus-visible:ring-offset-1",
                isActive
                  ? "border-accent-500/40 bg-accent-500/[0.06] ring-1 ring-accent-500/20"
                  : "border-border bg-secondary/30 hover:bg-secondary/60"
              )}
              onClick={() => setTheme(palette.id as Settings["theme"])}
            >
              <div
                className="w-full h-10 rounded-lg"
                style={{
                  background: `linear-gradient(135deg, ${palette.accent}, ${palette.accentEnd})`,
                }}
                aria-hidden
              />
              <span
                className={cn(
                  "text-sm font-medium",
                  isActive ? "text-cream" : "text-cream-muted"
                )}
              >
                {palette.name}
              </span>
              {isActive && (
                <span
                  className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-accent-500"
                  aria-hidden
                />
              )}
            </button>
          );
        })}
      </div>
    </fieldset>

    <div className="border-t border-border" />

    <div className="flex items-start justify-between gap-6">
      <div className="flex-1 min-w-0">
        <label
          htmlFor="onboarding-autostart"
          className="text-sm font-medium text-cream cursor-pointer"
        >
          Launch at login
        </label>
        <p className="text-xs text-cream-muted mt-1 leading-relaxed">
          Start Dictore when you sign in to your computer.
        </p>
      </div>
      <Switch
        id="onboarding-autostart"
        checked={autoStart}
        onCheckedChange={setAutoStart}
        className="mt-0.5 flex-shrink-0"
      />
    </div>
  </div>
);

// ============================================================================
// STEP: FINAL
// ============================================================================

const StepFinal = () => (
  <div className="space-y-5 max-w-lg w-full">
    <div className="border border-border rounded-md bg-surface p-8 space-y-5">
      <div className="text-center space-y-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 flex items-center justify-center gap-2">
          <Keyboard className="w-3 h-3 text-accent-500" strokeWidth={2.5} />
          global shortcut
        </p>
        <div className="flex items-center justify-center gap-3 pt-1">
          <kbd className="min-w-[72px] py-2.5 rounded-md bg-secondary border border-border text-base font-mono font-medium text-cream">
            Ctrl
          </kbd>
          <span className="text-base text-cream-muted/40 font-mono">+</span>
          <kbd className="min-w-[72px] py-2.5 rounded-md bg-secondary border border-border text-base font-mono font-medium text-cream">
            Win
          </kbd>
        </div>
        <p className="text-sm text-cream-muted">
          Hold to record, release to transcribe.
        </p>
      </div>
    </div>

    <div className="flex items-center gap-3 px-4 py-3 border-l-2 border-accent-500/40">
      <Sparkles
        className="w-4 h-4 text-accent-500 flex-shrink-0"
        strokeWidth={2}
      />
      <p className="text-sm text-cream-muted leading-relaxed">
        Dictore runs quietly in your system tray. Press the shortcut anytime,
        anywhere to start dictating.
      </p>
    </div>
  </div>
);

// ============================================================================
// STEP CONFIGURATION
// ============================================================================

const STEPS_CONFIG = [
  {
    id: "welcome",
    title: "Welcome to Dictore",
    subtitle: "Transform your voice into text with local AI processing.",
    icon: Sparkles,
  },
  {
    id: "audio",
    title: "Configure audio",
    subtitle: "Select your microphone and test the input levels.",
    icon: Mic,
  },
  {
    id: "hardware",
    title: "Hardware setup",
    subtitle: "Configure GPU acceleration for faster transcription.",
    icon: HardDrive,
  },
  {
    id: "model",
    title: "Choose model",
    subtitle: "Select the AI model and language for transcription.",
    icon: Cpu,
  },
  {
    id: "download",
    title: "Download model",
    subtitle: "Pulling weights — first run only, cached locally.",
    icon: Download,
  },
  {
    id: "theme",
    title: "Personalize",
    subtitle: "Choose your theme and startup preferences.",
    icon: Zap,
  },
  {
    id: "final",
    title: "You're all set",
    subtitle: "Start dictating with a simple keyboard shortcut.",
    icon: Check,
  },
];

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function Onboarding() {
  const navigate = useNavigate();
  const [options, setOptions] = useState<Options | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);

  const [language, setLanguage] = useState("auto");
  const [model, setModel] = useState("tiny");
  const [autoStart, setAutoStart] = useState(true);
  const [retention] = useState(-1);
  const [theme, setTheme] = useState<Settings["theme"]>("midnight");
  const [microphone, setMicrophone] = useState<number>(0);
  const [device, setDevice] = useState("auto");
  const [gpuInfo, setGpuInfo] = useState<GpuInfo | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        const [optionsData, gpuData] = await Promise.all([
          api.getOptions(),
          api.getGpuInfo(),
        ]);
        setOptions(optionsData);
        setGpuInfo(gpuData);
        if (optionsData.microphones.length > 0) {
          setMicrophone(optionsData.microphones[0].id);
        }
      } catch (err) {
        console.error("Failed to load options:", err);
        setError(
          "Failed to load configuration. Please restart the application."
        );
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const refreshGpuInfo = async () => {
    try {
      const gpuData = await api.getGpuInfo();
      setGpuInfo(gpuData);
    } catch (err) {
      console.error("Failed to refresh GPU info:", err);
    }
  };

  useEffect(() => {
    applyThemePalette(theme);
  }, [theme]);

  const handleFinish = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.updateSettings({
        language,
        model,
        autoStart,
        retention,
        theme,
        microphone,
        device,
        onboardingComplete: true,
      });
      navigate("/dashboard");
    } catch (err) {
      console.error("Failed to save settings:", err);
      setError("Failed to save settings. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const nextStep = () => setStep((s) => s + 1);
  const prevStep = () => setStep((s) => s - 1);

  const handleDownloadStart = () => setIsDownloading(true);
  const handleDownloadComplete = () => setIsDownloading(false);
  const handleDownloadCancel = () => {
    setIsDownloading(false);
    prevStep();
  };

  if (loading) {
    return (
      <main
        className="min-h-screen flex items-center justify-center bg-background bg-dots"
        aria-busy="true"
      >
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 rounded-full border-2 border-accent-500/30 border-t-accent-500 animate-spin" />
          <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-cream-muted/60">
            initializing dictore…
          </p>
        </div>
      </main>
    );
  }

  if (error && !options) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-background bg-dots px-6">
        <div
          className="border border-destructive/30 rounded-md bg-destructive/[0.03] p-8 max-w-md w-full text-center space-y-4"
          role="alert"
        >
          <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-destructive">
            initialization failed
          </p>
          <h2 className="font-display text-xl font-medium text-cream tracking-tight">
            Something went wrong
          </h2>
          <p className="text-sm text-cream-muted leading-relaxed">{error}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="h-10 px-5 rounded-md border border-border bg-secondary/40 hover:bg-secondary/60 transition-colors font-mono text-xs uppercase tracking-widest text-cream-muted hover:text-cream"
          >
            try again
          </button>
        </div>
      </main>
    );
  }

  if (!options) return null;

  const currentStepConfig = STEPS_CONFIG[step];
  const isLastStep = step === STEPS_CONFIG.length - 1;
  const isFirstStep = step === 0;
  const StepIcon = currentStepConfig.icon;

  const renderStepContent = () => {
    switch (step) {
      case 0:
        return <StepWelcome />;
      case 1:
        return (
          <StepAudio
            microphone={microphone}
            setMicrophone={setMicrophone}
            options={options}
          />
        );
      case 2:
        return (
          <StepHardware
            device={device}
            setDevice={setDevice}
            gpuInfo={gpuInfo}
            onGpuInfoUpdate={refreshGpuInfo}
          />
        );
      case 3:
        return (
          <StepModel
            language={language}
            setLanguage={setLanguage}
            model={model}
            setModel={setModel}
            options={options}
            device={device}
            gpuInfo={gpuInfo}
          />
        );
      case 4:
        return (
          <ModelDownloadProgress
            modelName={model}
            onStart={handleDownloadStart}
            onComplete={handleDownloadComplete}
            onCancel={handleDownloadCancel}
            autoStart={true}
          />
        );
      case 5:
        return (
          <StepTheme
            theme={theme}
            setTheme={setTheme}
            autoStart={autoStart}
            setAutoStart={setAutoStart}
          />
        );
      case 6:
        return <StepFinal />;
      default:
        return null;
    }
  };

  return (
    <main className="h-screen flex flex-col bg-background bg-dots overflow-hidden">
      {error && options && (
        <div
          role="alert"
          className="fixed top-4 left-1/2 -translate-x-1/2 z-50 border border-destructive/30 bg-destructive/[0.05] backdrop-blur rounded-md px-4 py-2 flex items-center gap-3"
        >
          <AlertCircle
            className="w-4 h-4 flex-shrink-0 text-destructive"
            strokeWidth={2}
          />
          <span className="font-mono text-xs text-destructive">{error}</span>
        </div>
      )}

      <div className="flex-1 flex flex-col px-6 md:px-10 lg:px-16 py-6 min-h-0">
        {/* Progress indicator */}
        <div
          className="flex justify-center gap-1.5 mb-6 flex-shrink-0"
          aria-label={`Step ${step + 1} of ${STEPS_CONFIG.length}`}
        >
          {STEPS_CONFIG.map((_, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => idx < step && setStep(idx)}
              disabled={idx > step}
              aria-label={`Go to step ${idx + 1}`}
              className={cn(
                "h-1 rounded-full transition-all duration-300",
                idx === step
                  ? "w-8 bg-accent-500"
                  : idx < step
                    ? "w-5 bg-accent-500/40 hover:bg-accent-500/60 cursor-pointer"
                    : "w-1.5 bg-cream-muted/20"
              )}
            />
          ))}
        </div>

        {/* Header */}
        <header className="text-center mb-8 flex-shrink-0 space-y-3 max-w-2xl mx-auto">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 flex items-center justify-center gap-2">
            <StepIcon
              className="w-3 h-3 text-accent-500"
              strokeWidth={2.5}
            />
            step {String(step + 1).padStart(2, "0")} / {String(STEPS_CONFIG.length).padStart(2, "0")}
            <span className="text-cream-muted/30 mx-1">·</span>
            <span>{currentStepConfig.id}</span>
          </p>
          <h1 className="font-display text-3xl md:text-4xl lg:text-5xl font-medium tracking-tight text-cream leading-[1.05]">
            {(() => {
              const words = currentStepConfig.title.split(" ");
              const last = words[words.length - 1];
              const rest = words.slice(0, -1).join(" ");
              return (
                <>
                  {rest && <>{rest} </>}
                  <span className="text-accent-500">{last}</span>
                </>
              );
            })()}
          </h1>
          <p className="text-sm md:text-base text-cream-muted leading-relaxed max-w-xl mx-auto">
            {currentStepConfig.subtitle}
          </p>
        </header>

        {/* Step Content */}
        <div className="flex-1 flex items-center justify-center min-h-0 overflow-hidden">
          {renderStepContent()}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-center gap-3 pt-6 flex-shrink-0">
          {!isFirstStep && (
            <Button
              variant="ghost"
              size="lg"
              onClick={prevStep}
              disabled={isDownloading}
              className="rounded-md text-cream-muted hover:text-cream hover:bg-secondary/60 px-5"
            >
              <ArrowLeft className="mr-2 w-4 h-4" strokeWidth={2} />
              Back
            </Button>
          )}

          <button
            type="button"
            onClick={isLastStep ? handleFinish : nextStep}
            disabled={saving || isDownloading}
            className="h-11 px-6 rounded-md min-w-[160px] bg-accent-500 text-zinc-950 hover:bg-accent-600 transition-colors font-medium text-sm flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                Saving…
              </>
            ) : isLastStep ? (
              <>
                Open dashboard
                <Check className="w-4 h-4" strokeWidth={2.5} />
              </>
            ) : (
              <>
                Continue
                <ArrowRight className="w-4 h-4" strokeWidth={2.5} />
              </>
            )}
          </button>
        </div>
      </div>

      <p className="text-center font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/40 pb-6">
        all processing happens locally · your voice never leaves your computer
      </p>
    </main>
  );
}
