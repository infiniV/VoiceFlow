import { useEffect, useMemo, useRef, useState } from "react";
import { Copy, Trash2, Search, Globe, FileAudio, X } from "lucide-react";
import { toast } from "sonner";
import { StatsHeader } from "@/components/StatsHeader";
import { RecordingOrb } from "@/components/RecordingOrb";
import { api } from "@/lib/api";
import type { HistoryEntry } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  base64ToBlobUrl,
  revokeUrl,
  isInvalidAudioPayload,
} from "@/lib/audio";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function HomePage() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showPlayer, setShowPlayer] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioMeta, setAudioMeta] = useState<{
    fileName?: string;
    mime?: string;
    durationMs?: number;
  } | null>(null);
  const [loadingAudioFor, setLoadingAudioFor] = useState<number | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordToggling, setRecordToggling] = useState(false);
  const [language, setLanguage] = useState("auto");
  const [rewritePreset, setRewritePreset] = useState("grammar_correct");
  const lastHistoryIdRef = useRef<number | null>(null);

  useEffect(() => {
    api.getSettings().then((s) => {
      setLanguage(s.language);
      setRewritePreset(s.rewritePreset ?? "grammar_correct");
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        const data = await api.getHistory(50, 0, undefined, false);
        setHistory(data);
        lastHistoryIdRef.current = data[0]?.id ?? null;
      } catch (err) {
        console.error("Failed to load history:", err);
        setError("Failed to load history. Please try again.");
        toast.error("Failed to load history");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Sync recording state with backend (covers hotkey-driven starts).
  // In-flight guard prevents request stacking when the RPC server slows
  // (observed: during long meeting recordings the asyncio RPC thread became
  // sluggish; without this guard, getRecordingState calls accumulated and
  // saturated aiohttp's accept queue, wedging the whole HTTP server).
  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    const tick = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const state = await api.getRecordingState();
        if (!cancelled) setIsRecording(state.recording);
      } catch {
        // backend may not be ready yet
      } finally {
        inFlight = false;
      }
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  // Refresh history after a recording stops so new entries appear without reload.
  useEffect(() => {
    if (isRecording) return;
    let cancelled = false;
    const refresh = async () => {
      await new Promise((r) => setTimeout(r, 600));
      if (cancelled) return;
      try {
        const data = await api.getHistory(50, 0, undefined, false);
        if (cancelled) return;
        const newest = data[0]?.id ?? null;
        if (newest !== null && newest !== lastHistoryIdRef.current) {
          setHistory(data);
          lastHistoryIdRef.current = newest;
        }
      } catch {
        // ignore
      }
    };
    refresh();
    return () => {
      cancelled = true;
    };
  }, [isRecording]);

  const handleToggleRecording = async () => {
    if (recordToggling) return;
    setRecordToggling(true);
    try {
      const result = await api.manualToggleRecording();
      setIsRecording(result.recording);
      if (result.error === "onboarding_active") {
        toast.error("Finish onboarding before recording");
      }
    } catch (e) {
      console.error("Failed to toggle recording:", e);
      toast.error("Failed to toggle recording");
    } finally {
      setRecordToggling(false);
    }
  };

  useEffect(() => () => revokeUrl(audioUrl), [audioUrl]);

  const handleCopy = async (text: string) => {
    try {
      await api.copyToClipboard(text);
      toast.success("Copied to clipboard");
    } catch {
      try {
        await navigator.clipboard.writeText(text);
        toast.success("Copied to clipboard");
      } catch {
        toast.error("Failed to copy to clipboard");
      }
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteHistory(id);
      setHistory((prev) => prev.filter((h) => h.id !== id));
      toast.success("Transcription deleted");
    } catch (err) {
      console.error("Failed to delete:", err);
      toast.error("Failed to delete transcription");
    }
  };

  const handlePlayAudio = async (historyId: number) => {
    setLoadingAudioFor(historyId);
    try {
      const response = await api.getHistoryAudio(historyId);
      revokeUrl(audioUrl);
      const url = base64ToBlobUrl(response.base64, response.mime);
      setAudioUrl(url);
      setAudioMeta({
        fileName: response.fileName,
        mime: response.mime,
        durationMs: response.durationMs,
      });
      setShowPlayer(true);
    } catch (err) {
      console.error("Failed to load audio recording:", err);
      toast.error(
        isInvalidAudioPayload(err)
          ? "Audio file is corrupted"
          : "Audio file not found"
      );
      revokeUrl(audioUrl);
      setAudioUrl(null);
      setShowPlayer(false);
      setAudioMeta(null);
    } finally {
      setLoadingAudioFor(null);
    }
  };

  const filteredHistory = useMemo(
    () =>
      history.filter((entry) =>
        entry.text.toLowerCase().includes(searchQuery.toLowerCase())
      ),
    [history, searchQuery]
  );

  const groupedHistory = useMemo(() => groupByDate(filteredHistory), [filteredHistory]);

  const todayStats = useMemo(() => {
    const today = new Date();
    const todayEntries = history.filter((h) =>
      isSameDay(new Date(h.created_at), today)
    );
    return {
      words: todayEntries.reduce((sum, h) => sum + h.word_count, 0),
      entries: todayEntries.length,
    };
  }, [history]);

  const durationMs = audioMeta?.durationMs;
  const groupedKeys = Object.keys(groupedHistory);
  const hasResults = groupedKeys.length > 0;

  return (
    <>
      <div className="min-h-full w-full bg-background relative overflow-hidden">
        {/* Ambient orbs — VoiceKey style */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
          <div className="orb orb-primary -top-32 -left-32" />
          <div className="orb orb-secondary top-1/3 -right-24" />
        </div>

        <div className="relative w-full max-w-5xl mx-auto px-6 md:px-10 py-8 md:py-12 space-y-12">
          {/* Record hero — iOS RecordingView parity */}
          <section className="flex flex-col items-center text-center pt-4 md:pt-8 pb-6">
            <div className="flex items-center gap-2 mb-8 self-start md:self-center">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full accent-gradient-bg text-white text-xs font-semibold tracking-wide">
                <Globe className="w-3 h-3" strokeWidth={2.5} />
                {language === "auto" ? "AUTO" : language.toUpperCase()}
              </span>
              <span className="text-[10px] font-mono uppercase tracking-widest text-cream-muted/50 px-2 py-1 rounded-full border border-border">
                {rewritePreset.replace(/_/g, " ")}
              </span>
            </div>

            <RecordingOrb
              isRecording={isRecording}
              onClick={handleToggleRecording}
              disabled={recordToggling}
              size="lg"
            />

            <p className="mt-8 text-sm text-cream-muted max-w-sm leading-relaxed">
              {isRecording
                ? "Listening… release your hotkey or tap the orb to stop."
                : "Tap the orb or press your hotkey anywhere to dictate."}
            </p>

            {isRecording && (
              <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.3em] text-recording-active">
                recording
              </p>
            )}
          </section>

          <StatsHeader todayStats={todayStats} />

          <div className="border-t border-border" />

          <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <h2 className="font-display text-xl font-medium text-cream tracking-tight">
                Recent
              </h2>
              <SearchBar
                value={searchQuery}
                onChange={setSearchQuery}
                count={filteredHistory.length}
              />
            </div>

          {loading ? (
            <LogSkeleton />
          ) : error ? (
            <LogError error={error} onRetry={() => window.location.reload()} />
          ) : !hasResults ? (
            <LogEmpty searchQuery={searchQuery} />
          ) : (
            <div className="space-y-10">
              {Object.entries(groupedHistory).map(([dateLabel, entries]) => (
                <LogSection
                  key={dateLabel}
                  label={dateLabel}
                  entries={entries}
                  onCopy={handleCopy}
                  onDelete={handleDelete}
                  onPlayAudio={handlePlayAudio}
                  loadingAudioFor={loadingAudioFor}
                />
              ))}
            </div>
          )}
          </div>
        </div>
      </div>

      <AudioPlayerDialog
        open={showPlayer}
        audioUrl={audioUrl}
        audioMeta={audioMeta}
        durationMs={durationMs}
        onOpenChange={(open) => {
          setShowPlayer(open);
          if (!open) {
            revokeUrl(audioUrl);
            setAudioUrl(null);
            setAudioMeta(null);
          }
        }}
      />
    </>
  );
}

function SearchBar({
  value,
  onChange,
  count,
}: {
  value: string;
  onChange: (v: string) => void;
  count: number;
}) {
  const hasQuery = value.length > 0;
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="relative flex-1 max-w-sm min-w-[200px]">
        <Search
          className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-cream-muted/60 pointer-events-none"
          strokeWidth={2}
        />
        <input
          type="text"
          placeholder="Search transcriptions"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full h-9 pl-9 pr-9 bg-secondary/30 border border-border rounded-md text-sm text-cream placeholder:text-cream-muted/50 focus:bg-secondary/50 focus:border-accent-500/40 focus:outline-none transition-colors"
        />
        {hasQuery && (
          <button
            type="button"
            onClick={() => onChange("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-cream-muted/60 hover:text-cream p-1 rounded transition-colors"
            aria-label="Clear search"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {hasQuery && (
        <span className="font-mono text-[11px] uppercase tracking-widest text-cream-muted/60">
          {count} {count === 1 ? "match" : "matches"}
        </span>
      )}
    </div>
  );
}

function LogSection({
  label,
  entries,
  onCopy,
  onDelete,
  onPlayAudio,
  loadingAudioFor,
}: {
  label: string;
  entries: HistoryEntry[];
  onCopy: (text: string) => void;
  onDelete: (id: number) => void;
  onPlayAudio: (id: number) => void;
  loadingAudioFor: number | null;
}) {
  return (
    <section>
      <div className="flex items-center gap-3 mb-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 whitespace-nowrap">
          {label}
          <span className="text-cream-muted/30 mx-2">·</span>
          <span className="text-cream-muted/40">
            {entries.length} {entries.length === 1 ? "entry" : "entries"}
          </span>
        </p>
        <div className="flex-1 h-px bg-border" />
      </div>
      <div>
        {entries.map((entry) => (
          <LogRow
            key={entry.id}
            entry={entry}
            onCopy={onCopy}
            onDelete={onDelete}
            onPlayAudio={onPlayAudio}
            isLoadingAudio={loadingAudioFor === entry.id}
          />
        ))}
      </div>
    </section>
  );
}

function LogRow({
  entry,
  onCopy,
  onDelete,
  onPlayAudio,
  isLoadingAudio,
}: {
  entry: HistoryEntry;
  onCopy: (text: string) => void;
  onDelete: (id: number) => void;
  onPlayAudio: (id: number) => void;
  isLoadingAudio: boolean;
}) {
  const hasAudio = !!entry.has_audio;
  return (
    <article className="group relative flex items-start gap-5 py-4 border-t border-border first:border-t-0 transition-colors hover:bg-secondary/[0.25] -mx-2 px-2 rounded-sm">
      <div className="flex flex-col items-end gap-1.5 w-14 flex-shrink-0 pt-0.5">
        <span className="font-mono text-[11px] text-cream-muted/70 leading-none">
          {formatTime(entry.created_at)}
        </span>
        {hasAudio && (
          <span
            className="font-mono text-[9px] uppercase tracking-[0.15em] text-accent-500/80 flex items-center gap-1 leading-none"
            title="Audio recording attached"
          >
            <FileAudio className="w-2.5 h-2.5" strokeWidth={2.5} />
            audio
          </span>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm leading-relaxed text-cream/90 line-clamp-3 group-hover:text-cream transition-colors break-words">
          {entry.text}
        </p>
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cream-muted/50 mt-2">
          {entry.word_count} {entry.word_count === 1 ? "word" : "words"}
        </p>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
        <RowAction
          icon={Copy}
          label="Copy"
          onClick={() => onCopy(entry.text)}
        />
        {hasAudio && (
          <RowAction
            icon={FileAudio}
            label={isLoadingAudio ? "Loading…" : "Play audio"}
            onClick={() => onPlayAudio(entry.id)}
            disabled={isLoadingAudio}
          />
        )}
        <RowAction
          icon={Trash2}
          label="Delete"
          tone="danger"
          onClick={() => onDelete(entry.id)}
        />
      </div>
    </article>
  );
}

function RowAction({
  icon: Icon,
  label,
  onClick,
  disabled,
  tone = "default",
}: {
  icon: React.ElementType;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "danger";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={cn(
        "h-8 w-8 rounded-md flex items-center justify-center transition-colors",
        "text-cream-muted/70 hover:bg-secondary/60",
        tone === "danger"
          ? "hover:text-destructive hover:bg-destructive/10"
          : "hover:text-cream",
        "disabled:opacity-40 disabled:cursor-not-allowed"
      )}
    >
      <Icon className="w-3.5 h-3.5" strokeWidth={2} />
    </button>
  );
}

function LogEmpty({ searchQuery }: { searchQuery: string }) {
  return (
    <div className="border border-dashed border-border rounded-md py-16 px-6 text-center space-y-3">
      <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-cream-muted/60">
        {searchQuery ? "no matches" : "log empty"}
      </p>
      <p className="text-sm text-cream-muted">
        {searchQuery
          ? `Nothing matches "${searchQuery}".`
          : "Your transcriptions will appear here as you dictate."}
      </p>
      {!searchQuery && (
        <p className="font-mono text-xs text-cream-muted/60 pt-2">
          <span className="text-cream-muted/40">→ </span>
          press your hotkey or use the{" "}
          <span className="text-accent-500">Record</span> button
        </p>
      )}
    </div>
  );
}

function LogError({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) {
  return (
    <div className="border border-destructive/30 bg-destructive/[0.03] rounded-md p-6 space-y-4">
      <div className="space-y-1">
        <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-destructive">
          read failed
        </p>
        <p className="text-sm text-cream">{error}</p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="h-9 px-4 rounded-md border border-border bg-secondary/40 hover:bg-secondary/60 hover:text-cream transition-colors font-mono text-[11px] uppercase tracking-widest text-cream-muted"
      >
        retry
      </button>
    </div>
  );
}

function LogSkeleton() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <div className="h-2 w-32 bg-secondary/50 rounded animate-pulse" />
        <div className="flex-1 h-px bg-border" />
      </div>
      <div>
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="flex items-start gap-5 py-4 border-t border-border first:border-t-0"
          >
            <div className="w-14 flex-shrink-0 flex justify-end">
              <div className="h-2.5 w-9 bg-secondary/50 rounded animate-pulse" />
            </div>
            <div className="flex-1 space-y-2">
              <div className="h-3 bg-secondary/40 rounded animate-pulse" />
              <div
                className="h-3 bg-secondary/40 rounded animate-pulse"
                style={{ width: `${50 + ((i * 13) % 40)}%` }}
              />
              <div className="h-2 w-16 bg-secondary/30 rounded animate-pulse mt-1" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AudioPlayerDialog({
  open,
  audioUrl,
  audioMeta,
  durationMs,
  onOpenChange,
}: {
  open: boolean;
  audioUrl: string | null;
  audioMeta: { fileName?: string; mime?: string; durationMs?: number } | null;
  durationMs?: number;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
            audio playback
          </p>
          <DialogTitle className="font-display text-xl font-medium tracking-tight text-cream truncate">
            {audioMeta?.fileName || "Recording"}
          </DialogTitle>
          <DialogDescription className="font-mono text-xs text-cream-muted">
            {durationMs
              ? `${Math.round(durationMs / 1000)}s · ${audioMeta?.mime || "audio/wav"}`
              : "Playback of the recorded audio"}
          </DialogDescription>
        </DialogHeader>
        {audioUrl ? (
          // biome-ignore lint/a11y/useMediaCaption: transcript text is shown in the log
          <audio controls autoPlay className="w-full">
            <source src={audioUrl} type={audioMeta?.mime || "audio/wav"} />
            Your browser does not support audio playback.
          </audio>
        ) : (
          <p className="text-sm text-cream-muted">No audio loaded.</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function groupByDate(entries: HistoryEntry[]): Record<string, HistoryEntry[]> {
  const groups: Record<string, HistoryEntry[]> = {};
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  for (const entry of entries) {
    const entryDate = new Date(entry.created_at);
    let label: string;

    if (isSameDay(entryDate, today)) {
      label = "today";
    } else if (isSameDay(entryDate, yesterday)) {
      label = "yesterday";
    } else {
      label = entryDate.toLocaleDateString([], {
        weekday: "long",
        month: "long",
        day: "numeric",
      });
    }

    if (!groups[label]) groups[label] = [];
    groups[label].push(entry);
  }

  return groups;
}

function isSameDay(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
}
