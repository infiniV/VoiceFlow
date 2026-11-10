import { useEffect, useState } from "react";
import { Download, X, Check, AlertCircle, Loader2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { huggingFaceUrl } from "@/lib/models";
import { useModelDownload } from "@/hooks/useModelDownload";

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

export function ModelDownloadProgress({
  modelName,
  onStart,
  onComplete,
  onCancel,
  autoStart = true,
}: ModelDownloadProgressProps) {
  const { state, progress, error, cancel, retry } = useModelDownload(modelName, {
    autoStart,
    onStart,
    onComplete,
    onCancel,
  });

  // Repo id powers the manual-download fallback in the error state. Fetched
  // once from the backend rather than hardcoding a URL map on the frontend.
  const [repoId, setRepoId] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    api
      .getModelInfo(modelName)
      .then((info) => active && setRepoId(info.repoId))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [modelName]);

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
    const hfUrl = huggingFaceUrl(repoId);

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
            <Button onClick={retry} variant="outline" className="rounded-xl">
              Try Again
            </Button>
            {hfUrl && (
              <Button
                variant="ghost"
                className="rounded-xl text-xs"
                onClick={() => api.openExternalUrl(hfUrl)}
              >
                <ExternalLink className="w-3 h-3 mr-1.5" />
                Download from HuggingFace
              </Button>
            )}
          </div>
        </div>

        {hfUrl && (
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
              <li>Restart VoiceFlow</li>
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
          <Button onClick={retry} variant="outline" className="rounded-xl">
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
                {state === "cancelling" ? "Stopping" : "Downloading"} {modelName}
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
        onClick={cancel}
        disabled={state === "cancelling"}
        className="w-full rounded-xl text-muted-foreground hover:text-destructive"
      >
        <X className="w-4 h-4 mr-2" />
        {state === "cancelling" ? "Waiting for the download to stop…" : "Cancel Download"}
      </Button>

      <p className="text-xs text-center text-muted-foreground">
        This downloads the AI model to your computer.
        <br />
        Your voice will be processed entirely offline.
      </p>
    </div>
  );
}
