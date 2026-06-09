/* Single-meeting view. Asymmetric split:
   - LEFT (wide reading column): editable summary, then full transcript
   - RIGHT (narrow rail): sticky audio player + metadata + actions */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  Download,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import type { LLMConfig, RecordingWithSegments } from "@/lib/types";
import { AudioPlayer, type AudioPlayerHandle } from "./AudioPlayer";
import { RetranscribeDialog } from "./RetranscribeDialog";
import { StatusLine } from "./StatusLine";
import { SummaryView } from "./SummaryView";
import { TranscriptView } from "./TranscriptView";
import { formatBytes, formatDuration } from "./utils";

export function MeetingDetailPage() {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = Number(params.id);

  const [recording, setRecording] = useState<RecordingWithSegments | null>(null);
  const [llmConfig, setLlmConfig] = useState<LLMConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [currentMs, setCurrentMs] = useState(0);
  const [retranscribeOpen, setRetranscribeOpen] = useState(false);

  const audioRef = useRef<AudioPlayerHandle>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.recordingsGet(id);
      setRecording(r);
      setTitleDraft(r.title);
    } catch (err) {
      console.error("get recording failed", err);
      toast.error("Could not load recording");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.llmGetConfig().then(setLlmConfig).catch(() => setLlmConfig(null));
  }, []);

  // Poll while a job is in progress.
  const isProcessing = useMemo(() => {
    if (!recording) return false;
    return (
      recording.transcriptStatus === "transcribing" ||
      recording.transcriptStatus === "pending" ||
      recording.summaryStatus === "summarizing"
    );
  }, [recording]);

  useEffect(() => {
    if (!isProcessing) return;
    const t = window.setInterval(() => {
      load();
    }, 1500);
    return () => window.clearInterval(t);
  }, [isProcessing, load]);

  const handleSaveTitle = async () => {
    if (!recording) return;
    if (titleDraft.trim() === recording.title) {
      setEditingTitle(false);
      return;
    }
    try {
      const updated = await api.recordingsUpdate(recording.id, {
        title: titleDraft.trim(),
      });
      setRecording({ ...recording, ...updated });
      setEditingTitle(false);
    } catch (err) {
      console.error(err);
      toast.error("Could not save title");
    }
  };

  const handleSaveSummary = async (next: string) => {
    if (!recording) return;
    const updated = await api.recordingsUpdate(recording.id, { summary: next });
    setRecording({ ...recording, ...updated });
    toast.success("Summary saved");
  };

  const handleRegenerate = async () => {
    if (!recording) return;
    try {
      await api.recordingsSummarize(recording.id);
      toast.success("Summarizing…");
      load();
    } catch (err) {
      console.error(err);
      toast.error("Could not start summarization");
    }
  };

  const handleExport = async (fmt: "txt" | "md" | "json" | "srt") => {
    if (!recording) return;
    try {
      const { path } = await api.recordingsExport(recording.id, fmt);
      toast.success(`Exported to ${path}`);
    } catch (err) {
      console.error(err);
      toast.error("Export failed");
    }
  };

  const handleDelete = async () => {
    if (!recording) return;
    try {
      await api.recordingsDelete(recording.id);
      toast.success("Recording deleted");
      navigate("/dashboard/meetings");
    } catch (err) {
      console.error(err);
      toast.error("Could not delete recording");
    }
  };

  if (loading) {
    return (
      <div className="min-h-full w-full bg-background flex items-center justify-center px-6 py-20">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 rounded-full border-2 border-accent-500/30 border-t-accent-500 animate-spin" />
          <p className="font-mono text-[11px] text-cream-muted/60 uppercase tracking-widest">
            loading recording…
          </p>
        </div>
      </div>
    );
  }

  if (!recording) {
    return (
      <div className="min-h-full w-full bg-background">
        <div className="w-full max-w-6xl mx-auto px-6 md:px-10 py-10 md:py-16 space-y-6">
          <Link
            to="/dashboard/meetings"
            className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 hover:text-accent-500 transition-colors inline-flex items-center gap-1.5"
          >
            <ArrowLeft className="w-3 h-3" />
            library
          </Link>
          <div className="border border-dashed border-border rounded-md py-20 px-6 text-center space-y-3 max-w-2xl mx-auto">
            <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-destructive/80">
              recording not found
            </p>
            <p className="text-sm text-cream-muted">
              It may have been deleted or moved. Head back to the library to
              pick another.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const audioSrc = recording.audioRelpath
    ? `dictore://recording/${recording.audioRelpath.split("/").pop()}`
    : null;

  const llmConfigured =
    !!llmConfig?.hasApiKey || llmConfig?.preset === "ollama";

  const sourceLabel =
    recording.sources.map((s) => (s === "mic" ? "mic" : "system")).join(" + ") ||
    "—";

  return (
    <div className="min-h-full w-full bg-background">
      <div className="w-full max-w-6xl mx-auto px-6 md:px-10 py-10 md:py-16 space-y-12">
        <Link
          to="/dashboard/meetings"
          className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 hover:text-accent-500 transition-colors inline-flex items-center gap-1.5"
        >
          <ArrowLeft className="w-3 h-3" />
          library
        </Link>

        <header className="space-y-4 max-w-4xl">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
            {formatDateLong(recording.createdAt)}
            <span className="text-cream-muted/30 mx-2">·</span>
            <span className="text-cream-muted/70">
              {formatDuration(recording.audioDurationMs)}
            </span>
            <span className="text-cream-muted/30 mx-2">·</span>
            <span className="text-cream-muted/70">{sourceLabel}</span>
          </p>

          {editingTitle ? (
            <div className="flex items-center gap-2">
              <Input
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveTitle();
                  if (e.key === "Escape") {
                    setTitleDraft(recording.title);
                    setEditingTitle(false);
                  }
                }}
                autoFocus
                className="font-display text-4xl md:text-5xl font-medium tracking-tight text-cream h-auto py-1 bg-transparent border-0 border-b border-accent-500/40 rounded-none px-0 focus-visible:ring-0 focus-visible:border-accent-500 leading-[1.05]"
              />
              <Button size="sm" variant="ghost" onClick={handleSaveTitle}>
                <Check className="w-4 h-4" />
              </Button>
            </div>
          ) : (
            <h1
              className="font-display text-4xl md:text-5xl font-medium tracking-tight text-cream leading-[1.05] cursor-text inline-flex items-baseline gap-3 group"
              onClick={() => setEditingTitle(true)}
            >
              {recording.title || (
                <span className="text-cream-muted">Untitled recording</span>
              )}
              <Pencil className="w-4 h-4 text-cream-muted/40 opacity-0 group-hover:opacity-100 transition-opacity" />
            </h1>
          )}

          <div>
            <StatusLine recording={recording} />
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_18rem] gap-12">
          {/* Reading column */}
          <div className="space-y-16 min-w-0">
            <SummaryView
              markdown={recording.summary}
              streaming={recording.summaryStatus === "summarizing"}
              llmConfigured={llmConfigured}
              onSave={handleSaveSummary}
              onRegenerate={handleRegenerate}
              onConfigureLLM={() => navigate("/dashboard/settings")}
            />

            <section className="space-y-4">
              <header className="flex items-baseline justify-between gap-4 flex-wrap">
                <div className="flex items-baseline gap-3 flex-wrap">
                  <h2 className="font-display text-2xl md:text-3xl font-medium tracking-tight text-cream leading-tight">
                    Transcript
                  </h2>
                  {recording.transcriptModel && (
                    <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-cream-muted/60 px-2 py-0.5 border border-border rounded-sm">
                      {recording.transcriptModel}
                    </span>
                  )}
                </div>
                {recording.transcriptStatus === "transcribing" && (
                  <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-accent-500 inline-flex items-center gap-1.5">
                    <span className="w-1 h-1 rounded-full bg-current animate-pulse" />
                    transcribing · {Math.round(recording.transcriptProgress * 100)}%
                  </span>
                )}
              </header>
              <TranscriptView
                segments={recording.segments}
                currentMs={currentMs}
                onSeek={(ms) => audioRef.current?.seekTo(ms)}
              />
            </section>
          </div>

          {/* Side rail */}
          <aside className="space-y-8 lg:sticky lg:top-6 lg:self-start">
            {audioSrc && (
              <div className="space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
                  audio
                </p>
                <AudioPlayer
                  ref={audioRef}
                  src={audioSrc}
                  durationMs={recording.audioDurationMs}
                  onTimeUpdate={setCurrentMs}
                />
              </div>
            )}

            <Metadata recording={recording} />

            <div className="space-y-2 pt-6 border-t border-border">
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start gap-2"
                disabled={
                  !recording.audioRelpath ||
                  recording.transcriptStatus === "transcribing" ||
                  recording.transcriptStatus === "pending"
                }
                onClick={() => setRetranscribeOpen(true)}
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Re-transcribe
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start gap-2"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Export
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-44">
                  <DropdownMenuItem onClick={() => handleExport("md")}>
                    Markdown (.md)
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport("txt")}>
                    Plain text (.txt)
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport("srt")}>
                    Subtitles (.srt)
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport("json")}>
                    Structured (.json)
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start gap-2 text-destructive hover:text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete recording
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle className="font-display tracking-tight">
                      Delete this recording?
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      The audio file, transcript, and summary will be removed
                      from your machine. This can't be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      onClick={handleDelete}
                    >
                      Delete
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </aside>
        </div>
      </div>

      <RetranscribeDialog
        open={retranscribeOpen}
        onOpenChange={setRetranscribeOpen}
        recording={recording}
        onStarted={load}
      />
    </div>
  );
}

function Metadata({ recording }: { recording: RecordingWithSegments }) {
  const rows: Array<[string, React.ReactNode]> = [
    ["duration", formatDuration(recording.audioDurationMs)],
    ["size", formatBytes(recording.audioSizeBytes)],
    [
      "channels",
      recording.audioChannels ? `${recording.audioChannels}` : "—",
    ],
    [
      "sample rate",
      recording.audioSampleRate ? `${recording.audioSampleRate} Hz` : "—",
    ],
    ["language", recording.language || "—"],
    [
      "provider",
      recording.summaryProvider ? (
        <span className="font-mono text-[11px]">{recording.summaryProvider}</span>
      ) : (
        "—"
      ),
    ],
  ];
  return (
    <dl className="font-mono text-[12px] grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5">
      {rows.map(([k, v]) => (
        <div key={String(k)} className="contents">
          <dt className="text-cream-muted/60 uppercase tracking-widest text-[10px] self-center">
            {k}
          </dt>
          <dd className="text-cream tabular-figs text-right truncate">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function formatDateLong(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
