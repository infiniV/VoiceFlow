import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { api } from "@/lib/api";

const DISMISS_KEY = "dictore:hotkey-banner-dismissed-code";

export function HotkeyStatusBanner() {
  const [status, setStatus] = useState<{
    available: boolean;
    code: string;
    message: string;
  } | null>(null);
  const [dismissedCode, setDismissedCode] = useState<string | null>(() => {
    try {
      return localStorage.getItem(DISMISS_KEY);
    } catch {
      return null;
    }
  });

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const s = await api.getHotkeyStatus();
        if (!cancelled) setStatus(s);
      } catch {
        // ignore
      }
    };
    check();
    // Re-check periodically — user may add themselves to the input group
    // and re-launch services without restarting the app.
    const id = window.setInterval(check, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (!status || status.available) return null;
  if (status.code === dismissedCode) return null;

  const handleDismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, status.code);
    } catch {
      // ignore
    }
    setDismissedCode(status.code);
  };

  return (
    <div className="bg-amber-500/10 border-b border-amber-500/30 px-4 md:px-8 py-3 flex items-start gap-3 text-sm">
      <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="font-medium text-amber-700 dark:text-amber-300">
          Global hotkeys are disabled
        </p>
        <p className="text-amber-700/80 dark:text-amber-300/80 mt-0.5">
          {status.message} You can still use the Record button on the dashboard.
        </p>
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        className="text-amber-700/60 dark:text-amber-300/60 hover:text-amber-700 dark:hover:text-amber-300 p-1 -m-1"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
