import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useBackendEvent } from "@/hooks/useBackendEvent";
import type { DownloadProgress, DownloadComplete } from "@/lib/types";

export type DownloadState =
  | "idle"
  | "downloading"
  | "cancelling"
  | "completed"
  | "cancelled"
  | "error";

interface UseModelDownloadOptions {
  /** Begin downloading as soon as the hook mounts (default true). */
  autoStart?: boolean;
  onStart?: () => void;
  onComplete?: (success: boolean) => void;
  onCancel?: () => void;
}

interface UseModelDownload {
  state: DownloadState;
  progress: DownloadProgress | null;
  error: string | null;
  start: () => Promise<void>;
  cancel: () => Promise<void>;
  retry: () => void;
}

/**
 * Owns the model-download state machine for one model.
 *
 * Before this hook the machine (5 states, 2 event subscriptions, start/cancel/
 * retry) was re-implemented inline by ModelDownloadProgress and re-wired by
 * SettingsTab, Onboarding, and the recovery/download modals. Now there is one
 * interface and one place to test it.
 *
 * On mount it queries getDownloadStatus(): if a download for this model is
 * already in flight (e.g. the user navigated away and came back), it re-attaches
 * to that session instead of starting a duplicate.
 */
export function useModelDownload(
  modelName: string,
  { autoStart = true, onStart, onComplete, onCancel }: UseModelDownloadOptions = {}
): UseModelDownload {
  const [state, setState] = useState<DownloadState>("idle");
  const [progress, setProgress] = useState<DownloadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hasStarted = useRef(false);

  // Only react to events for the model this hook tracks. The backend
  // single-flights downloads, but filtering keeps stale events from a
  // previous model out of this instance's state.
  useBackendEvent<DownloadProgress>("download-progress", (p) => {
    if (p.model === modelName) setProgress(p);
  });

  useBackendEvent<DownloadComplete>("download-complete", (result) => {
    if (result.model !== modelName) return;
    if (result.success) {
      setState("completed");
      onComplete?.(true);
    } else if (result.cancelled) {
      setState("cancelled");
      onCancel?.();
    } else {
      setState("error");
      setError(result.error || "Download failed");
      onComplete?.(false);
    }
  });

  const start = useCallback(async () => {
    try {
      setError(null);
      setState("downloading");
      onStart?.();
      const result = await api.startModelDownload(modelName);
      if (!result.success) throw new Error("Failed to start download");
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "Failed to start download");
    }
    // onStart is stable in practice; intentionally not a dep to avoid resubscribing
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelName]);

  const cancel = useCallback(async () => {
    try {
      const result = await api.cancelModelDownload();
      if (result.cancelled) {
        setState((current) => current === "downloading" ? "cancelling" : current);
      }
    } catch (err) {
      console.error("Failed to cancel download:", err);
    }
  }, []);

  const retry = useCallback(() => {
    hasStarted.current = false;
    setState("idle");
    setError(null);
    setProgress(null);
    void start();
  }, [start]);

  // On mount: re-attach to an in-flight download for this model, else autoStart.
  //
  // The hasStarted ref guards against a double launch. We deliberately do NOT
  // abort this run on effect cleanup: under React StrictMode the mount effect
  // is invoked twice on the same instance (mount → cleanup → mount), so an
  // abort-on-cleanup flag would cancel the only launched run while the ref
  // guard blocks the retry — and the download would never start.
  useEffect(() => {
    if (!autoStart || hasStarted.current) return;
    hasStarted.current = true;

    (async () => {
      try {
        const status = await api.getDownloadStatus();
        if (status.active && status.model === modelName) {
          setState(status.cancelling ? "cancelling" : "downloading");
          setProgress({
            model: modelName,
            percent: status.percent ?? 0,
            downloadedBytes: status.downloadedBytes ?? 0,
            totalBytes: status.totalBytes ?? 0,
            speedBps: status.speedBps ?? 0,
            etaSeconds: status.etaSeconds ?? 0,
          });
          onStart?.();
          return;
        }
      } catch {
        // Status probe failed — fall through to a normal start.
      }
      void start();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelName, autoStart, start]);

  return { state, progress, error, start, cancel, retry };
}
