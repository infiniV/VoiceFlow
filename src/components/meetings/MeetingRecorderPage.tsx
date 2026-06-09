/* Recorder UI.

   Two states:
     - PRE-RECORD: title input, source pickers (mic + system audio), Start.
     - LIVE: large tabular-num timer, REC indicator, twin level meters.

   Layout matches the rest of the app: standard page shell + `SettingRow`-style
   form rows so the visual rhythm tracks Settings. */

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Mic, Monitor, Pause, Play, Square } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import type { AudioSource } from "@/lib/types";
import { cn } from "@/lib/utils";
import { LevelMeter } from "./LevelMeter";
import { useMeetingRecorder } from "./MeetingRecorderContext";
import { formatDuration } from "./utils";

const NONE_VALUE = "__none__";

export function MeetingRecorderPage() {
  const navigate = useNavigate();
  const recorder = useMeetingRecorder();
  const isLive = recorder.isLive;

  const [sources, setSources] = useState<{
    mic: AudioSource[];
    loopback: AudioSource[];
  }>({ mic: [], loopback: [] });
  const [title, setTitle] = useState(defaultTitle());
  const [micId, setMicId] = useState<string>("");
  const [loopId, setLoopId] = useState<string>("");
  const [starting, setStarting] = useState(false);
  const [loadingSources, setLoadingSources] = useState(true);

  // Pre-record source preview — opens the picked source(s) without recording
  // so the user can confirm levels are flowing.
  const [previewMicDb, setPreviewMicDb] = useState<number | null>(null);
  const [previewLoopDb, setPreviewLoopDb] = useState<number | null>(null);
  const previewActiveKey = useRef<string>("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api.recordingsListAudioSources();
        if (cancelled) return;
        setSources(list);
        const defaultMic = list.mic.find((s) => s.isDefault) ?? list.mic[0];
        const defaultLoop =
          list.loopback.find((s) => s.isDefault) ?? list.loopback[0];
        if (defaultMic) setMicId(String(defaultMic.id));
        if (defaultLoop) setLoopId(String(defaultLoop.id));
      } catch (err) {
        console.warn("audio sources unavailable", err);
      } finally {
        if (!cancelled) setLoadingSources(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Drive the source preview from the currently-picked dropdown values.
  useEffect(() => {
    if (isLive) {
      previewActiveKey.current = "";
      return;
    }
    const key = `${micId || "-"}|${loopId || "-"}`;
    if (key === "-|-") {
      previewActiveKey.current = "";
      api.recordingsPreviewStop().catch(() => {});
      setPreviewMicDb(null);
      setPreviewLoopDb(null);
      return;
    }
    previewActiveKey.current = key;
    let cancelled = false;
    (async () => {
      const result = await api
        .recordingsPreviewStart(
          micId ? Number(micId) : null,
          loopId ? Number(loopId) : null,
        )
        .catch((err: unknown) => {
          console.warn("preview start failed", err);
          return { ok: false } as const;
        });
      if (cancelled || previewActiveKey.current !== key) return;
      if (!result.ok) {
        setPreviewMicDb(null);
        setPreviewLoopDb(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [micId, loopId, isLive]);

  useEffect(() => {
    return () => {
      api.recordingsPreviewStop().catch(() => {});
    };
  }, []);

  useEffect(() => {
    if (isLive) return;
    const hasAny = micId !== "" || loopId !== "";
    if (!hasAny) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const st = await api.recordingsPreviewState();
        if (cancelled) return;
        setPreviewMicDb(st.hasMic ? st.micPeakDb : null);
        setPreviewLoopDb(st.hasLoopback ? st.loopbackPeakDb : null);
      } catch {
        /* RPC blip — keep last value. */
      }
    };
    tick();
    const id = window.setInterval(tick, 200);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [micId, loopId, isLive]);

  const handleStart = async () => {
    if (!micId && !loopId) {
      toast.error("Pick at least one source");
      return;
    }
    setStarting(true);
    try {
      previewActiveKey.current = "";
      setPreviewMicDb(null);
      setPreviewLoopDb(null);
      await api.recordingsStart(
        title || defaultTitle(),
        micId ? Number(micId) : null,
        loopId ? Number(loopId) : null,
      );
      await recorder.refresh();
    } catch (err) {
      console.error("start failed", err);
      toast.error("Could not start recording");
    } finally {
      setStarting(false);
    }
  };

  const handlePauseToggle = async () => {
    try {
      if (recorder.state.state === "paused") {
        await api.recordingsResume();
      } else {
        await api.recordingsPause();
      }
      await recorder.refresh();
    } catch (err) {
      toast.error("Pause/resume failed");
      console.error(err);
    }
  };

  const handleStop = async () => {
    try {
      const rec = await api.recordingsStop();
      await recorder.refresh();
      toast.success("Recording saved · transcription queued");
      navigate(`/dashboard/meetings/${rec.id}`);
    } catch (err) {
      console.error("stop failed", err);
      toast.error("Could not stop recording");
    }
  };

  return (
    <div className="min-h-full w-full bg-background">
      <div className="w-full max-w-3xl mx-auto px-6 md:px-10 py-10 md:py-16 space-y-10">
        <button
          type="button"
          onClick={() => navigate("/dashboard/meetings")}
          className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 hover:text-accent-500 transition-colors inline-flex items-center gap-1.5"
        >
          <ArrowLeft className="w-3 h-3" />
          library
        </button>

        {isLive ? (
          <LiveRecorder
            durationMs={recorder.state.durationMs}
            paused={recorder.state.state === "paused"}
            micPeakDb={recorder.state.micPeakDb}
            loopbackPeakDb={recorder.state.loopbackPeakDb}
            onPauseToggle={handlePauseToggle}
            onStop={handleStop}
          />
        ) : (
          <PreRecordForm
            title={title}
            onTitle={setTitle}
            sources={sources}
            loadingSources={loadingSources}
            micId={micId}
            onMic={setMicId}
            loopId={loopId}
            onLoop={setLoopId}
            previewMicDb={previewMicDb}
            previewLoopDb={previewLoopDb}
            onStart={handleStart}
            starting={starting}
          />
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function PreRecordForm(props: {
  title: string;
  onTitle(v: string): void;
  sources: { mic: AudioSource[]; loopback: AudioSource[] };
  loadingSources: boolean;
  micId: string;
  onMic(v: string): void;
  loopId: string;
  onLoop(v: string): void;
  previewMicDb: number | null;
  previewLoopDb: number | null;
  onStart(): void;
  starting: boolean;
}) {
  const canStart = props.micId !== "" || props.loopId !== "";
  return (
    <>
      <header className="space-y-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
          01 / New recording
        </p>
        <h1 className="font-display text-4xl md:text-5xl font-medium tracking-tight text-cream leading-[1.05]">
          New meeting
        </h1>
        <p className="text-sm text-cream-muted max-w-xl leading-relaxed">
          Pick your audio sources, hit start, and Dictore streams to disk.
          You can pause whenever — silence is written so the timeline stays
          aligned.
        </p>
      </header>

      <section className="space-y-0">
        <SettingRow
          label="Title"
          helper="A short label so you can find this recording later."
        >
          <Input
            value={props.title}
            onChange={(e) => props.onTitle(e.target.value)}
            placeholder="Untitled meeting"
            className="h-10"
          />
        </SettingRow>

        <SourceRow
          label="Microphone"
          icon={Mic}
          helper="Your voice. Defaults to your system input."
          options={props.sources.mic}
          value={props.micId}
          onChange={props.onMic}
          loading={props.loadingSources}
          emptyHint="No microphone detected"
          previewDb={props.previewMicDb}
        />

        <SourceRow
          label="System audio"
          icon={Monitor}
          helper="The other side of a Teams / Meet / Zoom call. Captured via loopback."
          options={props.sources.loopback}
          value={props.loopId}
          onChange={props.onLoop}
          loading={props.loadingSources}
          emptyHint={
            props.loadingSources
              ? "Looking for loopback sources…"
              : "No system-audio source available on this machine"
          }
          previewDb={props.previewLoopDb}
        />
      </section>

      <div className="pt-6 border-t border-border flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-cream-muted max-w-md leading-relaxed">
          Recording is local. Audio never leaves your machine unless you
          explicitly export it.
        </p>
        <Button
          size="lg"
          onClick={props.onStart}
          disabled={!canStart || props.starting}
          className="gap-2 px-6"
        >
          <span className="w-2 h-2 rounded-full bg-current" aria-hidden />
          {props.starting ? "Starting…" : "Start recording"}
        </Button>
      </div>
    </>
  );
}

function SettingRow({
  label,
  helper,
  children,
}: {
  label: string;
  helper?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="py-5 border-t border-border first:border-t-0 flex flex-col gap-3 md:flex-row md:items-start md:justify-between md:gap-8">
      <div className="md:max-w-md">
        <p className="text-sm font-medium text-cream">{label}</p>
        {helper && (
          <p className="text-xs text-cream-muted mt-1 leading-relaxed">
            {helper}
          </p>
        )}
      </div>
      <div className="md:flex-shrink-0 md:w-80">{children}</div>
    </div>
  );
}

function SourceRow({
  label,
  icon: Icon,
  helper,
  options,
  value,
  onChange,
  loading,
  emptyHint,
  previewDb,
}: {
  label: string;
  icon: React.ElementType;
  helper: string;
  options: AudioSource[];
  value: string;
  onChange(v: string): void;
  loading: boolean;
  emptyHint: string;
  previewDb: number | null;
}) {
  const selectValue = value === "" ? NONE_VALUE : value;
  const isPicked = value !== "";

  return (
    <SettingRow label={label} helper={helper}>
      <div className="space-y-2.5">
        {options.length === 0 && !loading ? (
          <p className="text-sm text-cream-muted">{emptyHint}</p>
        ) : (
          <Select
            value={selectValue}
            onValueChange={(v) => onChange(v === NONE_VALUE ? "" : v)}
            disabled={loading || options.length === 0}
          >
            <SelectTrigger className="h-10 rounded-md font-mono text-sm bg-secondary/40 border-border hover:bg-secondary/60 transition-colors">
              <div className="flex items-center gap-2 min-w-0">
                <Icon className="w-3.5 h-3.5 text-cream-muted/70 flex-shrink-0" />
                <SelectValue placeholder={loading ? "Loading…" : "Choose…"} />
              </div>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE} className="font-mono text-sm">
                <span className="text-cream-muted">— Don't record this source —</span>
              </SelectItem>
              {options.map((src) => (
                <SelectItem
                  key={src.id}
                  value={String(src.id)}
                  className="font-mono text-sm"
                >
                  <span className="truncate">{src.name}</span>
                  <span className="font-mono text-[10px] text-cream-muted/70 ml-2">
                    {src.hostApi}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {isPicked && <SourcePreviewBar peakDb={previewDb} />}
      </div>
    </SettingRow>
  );
}

function SourcePreviewBar({ peakDb }: { peakDb: number | null }) {
  const FLOOR_DB = -60;
  const live = peakDb != null && peakDb > FLOOR_DB;
  const pct =
    peakDb == null
      ? 0
      : peakDb >= 0
        ? 100
        : peakDb <= FLOOR_DB
          ? 0
          : ((peakDb - FLOOR_DB) / -FLOOR_DB) * 100;
  const overload = peakDb != null && peakDb > -6;

  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60 w-14 shrink-0">
        live in
      </span>
      <div className="flex-1 relative h-px bg-border overflow-visible">
        <div
          className={cn(
            "absolute inset-y-[-1px] left-0 transition-[width] duration-75 ease-out",
            overload ? "bg-destructive" : "bg-accent-500",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span
        className={cn(
          "font-mono text-[10px] tabular-figs w-12 text-right",
          live ? "text-cream-muted" : "text-cream-muted/40",
        )}
      >
        {peakDb == null
          ? "—"
          : peakDb <= FLOOR_DB
            ? "silent"
            : `${peakDb.toFixed(0)} dB`}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function LiveRecorder(props: {
  durationMs: number;
  paused: boolean;
  micPeakDb: number | null;
  loopbackPeakDb: number | null;
  onPauseToggle(): void;
  onStop(): void;
}) {
  return (
    <section className="space-y-14 pt-6">
      <div className="text-center space-y-6">
        <p
          className={cn(
            "font-mono text-[10px] uppercase tracking-[0.3em] inline-flex items-center gap-2",
            props.paused ? "text-cream-muted/70" : "text-destructive",
          )}
        >
          {props.paused ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-cream-muted/70" />
              paused
            </>
          ) : (
            <>
              <span className="rec-pulse" />
              recording
            </>
          )}
        </p>
        <h1 className="font-display tabular-figs text-7xl md:text-[7rem] font-medium leading-none text-cream tracking-tight">
          {formatDuration(props.durationMs)}
        </h1>
      </div>

      <div className="max-w-md mx-auto space-y-4">
        <LevelMeter label="you" peakDb={props.micPeakDb} muted={props.paused} />
        <LevelMeter
          label="them"
          peakDb={props.loopbackPeakDb}
          muted={props.paused}
        />
      </div>

      <div className="flex items-center justify-center gap-3 pt-2">
        <Button
          variant="outline"
          size="lg"
          onClick={props.onPauseToggle}
          className="gap-2 h-12 px-6"
        >
          {props.paused ? (
            <>
              <Play className="w-4 h-4" />
              Resume
            </>
          ) : (
            <>
              <Pause className="w-4 h-4" />
              Pause
            </>
          )}
        </Button>
        <Button
          variant="destructive"
          size="lg"
          onClick={props.onStop}
          className="gap-2 h-12 px-6"
        >
          <Square className="w-4 h-4" fill="currentColor" />
          Stop & save
        </Button>
      </div>
    </section>
  );
}

function defaultTitle(): string {
  const d = new Date();
  return d.toLocaleString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
