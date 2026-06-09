import { useEffect, useState, useCallback, useRef } from "react";
import { Download, X, Check, AlertCircle, Loader2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import type { DownloadProgress, DownloadComplete } from "@/lib/types";

// HuggingFace URLs for manual download
const MODEL_HUGGINGFACE_URLS: Record<string, string> = {
  "tiny": "https://huggingface.co/Systran/faster-whisper-tiny",
  "base": "https://huggingface.co/Systran/faster-whisper-base",
  "small": "https://huggingface.co/Systran/faster-whisper-small",
  "medium": "https://huggingface.co/Systran/faster-whisper-medium",
  "large-v1": "https://huggingface.co/Systran/faster-whisper-large-v1",
  "large-v2": "https://huggingface.co/Systran/faster-whisper-large-v2",
  "large-v3": "https://huggingface.co/Systran/faster-whisper-large-v3",
  "turbo": "https://huggingface.co/Systran/faster-whisper-large-v3-turbo",
  "tiny.en": "https://huggingface.co/Systran/faster-whisper-tiny.en",
  "base.en": "https://huggingface.co/Systran/faster-whisper-base.en",
  "small.en": "https://huggingface.co/Systran/faster-whisper-small.en",
  "medium.en": "https://huggingface.co/Systran/faster-whisper-medium.en",
  "distil-small.en": "https://huggingface.co/Systran/faster-distil-whisper-small.en",
  "distil-medium.en": "https://huggingface.co/Systran/faster-distil-whisper-medium.en",
  "distil-large-v2": "https://huggingface.co/Systran/faster-distil-whisper-large-v2",
  "distil-large-v3": "https://huggingface.co/Systran/faster-distil-whisper-large-v3",
};

interface ModelDownloadProgressProps {
  modelName: string;
  onStart?: () => void;
  onComplete: (success: boolean) => void;
  onCancel?: () => void;
  autoStart?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatSpeed(bytesPerSecond: number): string {
  return `${formatBytes(bytesPerSecond)}/s`;
}

function formatEta(seconds: number): string {
  if (seconds <= 0 || !isFinite(seconds)) return "--:--";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

type DownloadState = "idle" | "downloading" | "completed" | "cancelled" | "error";

export function ModelDownloadProgress({
  modelName,
  onStart,
  onComplete,
  onCancel,
  autoStart = true,
}: ModelDownloadProgressProps) {
  const [state, setState] = useState<DownloadState>("idle");
  const [progress, setProgress] = useState<DownloadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hasStarted = useRef(false);

  // Handle download progress events
  const handleProgress = useCallback((e: CustomEvent<DownloadProgress>) => {
    setProgress(e.detail);
  }, []);

  // Handle download complete events
  const handleCompleteEvent = useCallback(
    (e: CustomEvent<DownloadComplete>) => {
      const result = e.detail;

      if (result.success) {
        setState("completed");
        onComplete(true);
      } else if (result.cancelled) {
        setState("cancelled");
        onCancel?.();
      } else {
        setState("error");
        setError(result.error || "Download failed");
        onComplete(false);
      }
    },
    [onComplete, onCancel]
  );

  // Set up event listeners
  useEffect(() => {
    document.addEventListener("download-progress", handleProgress as EventListener);
    document.addEventListener("download-complete", handleCompleteEvent as EventListener);

    return () => {
      document.removeEventListener("download-progress", handleProgress as EventListener);
      document.removeEventListener("download-complete", handleCompleteEvent as EventListener);
    };
  }, [handleProgress, handleCompleteEvent]);

  // Auto-start download
  useEffect(() => {
    if (autoStart && !hasStarted.current && state === "idle") {
      hasStarted.current = true;
      startDownload();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- startDownload is guarded by hasStarted.current ref
  }, [autoStart, state]);

  const startDownload = async () => {
    try {
      setError(null);

      const result = await api.startModelDownload(modelName);

      if (result.alreadyCached) {
        // Model was already cached, show completed state immediately
        setState("completed");
      } else {
        // Actually downloading - notify parent
        setState("downloading");
        onStart?.();
      }
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "Failed to start download");
    }
  };

  const handleCancel = async () => {
    try {
      await api.cancelModelDownload();
      // Don't update state here - wait for the complete event
    } catch (err) {
      console.error("Failed to cancel download:", err);
    }
  };

  const handleRetry = () => {
    hasStarted.current = false;
    setState("idle");
    setError(null);
    setProgress(null);
    startDownload();
  };

  // Render based on state
  if (state === "completed") {
    return (
      <div className="space-y-4">
        <div className="glass-card p-6 text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Check className="w-6 h-6 text-primary" />
          </div>
          <p className="text-lg font-medium text-foreground mb-1">
            Model Ready
          </p>
          <p className="text-sm text-muted-foreground">
            {modelName} is ready to use
          </p>
        </div>
      </div>
    );
  }

  if (state === "error") {
    const huggingFaceUrl = MODEL_HUGGINGFACE_URLS[modelName];

    return (
      <div className="space-y-4 max-w-md w-full">
        <div className="glass-card p-6 text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-destructive/10 border border-destructive/20 flex items-center justify-center">
            <AlertCircle className="w-6 h-6 text-destructive" />
          </div>
          <p className="text-lg font-medium text-foreground mb-1">
            Download Failed
          </p>
          <p className="text-sm text-muted-foreground mb-4">
            {error || "An error occurred"}
          </p>
          <div className="flex flex-col gap-2">
            <Button onClick={handleRetry} variant="outline" className="rounded-xl">
              Try Again
            </Button>
            {huggingFaceUrl && (
              <Button
                variant="ghost"
                className="rounded-xl text-xs"
                onClick={() => api.openExternalUrl(huggingFaceUrl)}
              >
                <ExternalLink className="w-3 h-3 mr-1.5" />
                Download from HuggingFace
              </Button>
            )}
          </div>
        </div>

        {huggingFaceUrl && (
          <div className="glass-card p-4 text-left">
            <p className="text-xs font-medium text-foreground mb-2">Manual Download Instructions:</p>
            <ol className="text-xs text-muted-foreground space-y-1.5 list-decimal list-inside">
              <li>Click "Download from HuggingFace" above</li>
              <li>Download all files (model.bin, config.json, etc.)</li>
              <li>
                Place files in:<br />
                <code className="text-[10px] bg-muted/50 px-1.5 py-0.5 rounded mt-1 inline-block break-all">
                  %USERPROFILE%\.cache\huggingface\hub\
                </code>
              </li>
              <li>Restart Dictore</li>
            </ol>
          </div>
        )}
      </div>
    );
  }

  if (state === "cancelled") {
    return (
      <div className="space-y-4">
        <div className="glass-card p-6 text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-muted/50 border border-border flex items-center justify-center">
            <X className="w-6 h-6 text-muted-foreground" />
          </div>
          <p className="text-lg font-medium text-foreground mb-1">
            Download Cancelled
          </p>
          <p className="text-sm text-muted-foreground mb-4">
            The model download was cancelled
          </p>
          <Button onClick={handleRetry} variant="outline" className="rounded-xl">
            Start Again
          </Button>
        </div>
      </div>
    );
  }

  // Downloading state
  return (
    <div className="space-y-6 max-w-md w-full">
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
              {state === "downloading" ? (
                <Download className="w-5 h-5 text-primary" />
              ) : (
                <Loader2 className="w-5 h-5 text-primary animate-spin" />
              )}
            </div>
            <div>
              <p className="font-medium text-foreground">
                Downloading {modelName}
              </p>
              <p className="text-xs text-muted-foreground">
                AI model for transcription
              </p>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <Progress
            value={progress?.percent || 0}
            className="h-2"
          />

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {progress
                ? `${formatBytes(progress.downloadedBytes)} / ${formatBytes(progress.totalBytes)}`
                : "Starting..."}
            </span>
            <span>{progress ? `${Math.round(progress.percent)}%` : "0%"}</span>
          </div>

          {progress && progress.speedBps > 0 && (
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{formatSpeed(progress.speedBps)}</span>
              <span>ETA: {formatEta(progress.etaSeconds)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Cancel button */}
      <Button
        variant="ghost"
        onClick={handleCancel}
        className="w-full rounded-xl text-muted-foreground hover:text-destructive"
      >
        <X className="w-4 h-4 mr-2" />
        Cancel Download
      </Button>

      <p className="text-xs text-center text-muted-foreground">
        This downloads the AI model to your computer.
        <br />
        Your voice will be processed entirely offline.
      </p>
    </div>
  );
}
