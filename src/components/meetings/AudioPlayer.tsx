/* Custom-styled audio player.

   Streams the recording via the `dictore://recording/<filename>.wav` URL
   scheme registered in main.py (slice 8) — the HTML5 <audio> element handles
   the Range requests natively. Exposes `seekTo(ms)` via a forwarded ref so the
   transcript view can scroll-and-seek on segment click. */

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { Pause, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDuration } from "./utils";

export interface AudioPlayerHandle {
  seekTo(ms: number): void;
  pause(): void;
}

interface AudioPlayerProps {
  src: string;
  durationMs: number | null;
  onTimeUpdate?(ms: number): void;
  className?: string;
}

export const AudioPlayer = forwardRef<AudioPlayerHandle, AudioPlayerProps>(
  function AudioPlayer({ src, durationMs, onTimeUpdate, className }, ref) {
    const audioRef = useRef<HTMLAudioElement>(null);
    const [playing, setPlaying] = useState(false);
    const [currentMs, setCurrentMs] = useState(0);
    const [resolvedDurationMs, setResolvedDurationMs] = useState<number | null>(
      durationMs ?? null,
    );

    useImperativeHandle(
      ref,
      () => ({
        seekTo(ms: number) {
          const audio = audioRef.current;
          if (!audio) return;
          audio.currentTime = Math.max(0, ms / 1000);
          if (audio.paused) {
            audio.play().catch(() => {});
          }
        },
        pause() {
          audioRef.current?.pause();
        },
      }),
      [],
    );

    const handlePlay = useCallback(() => {
      const audio = audioRef.current;
      if (!audio) return;
      if (audio.paused) {
        audio.play().catch(() => {});
      } else {
        audio.pause();
      }
    }, []);

    useEffect(() => {
      const audio = audioRef.current;
      if (!audio) return;
      const onPlay = () => setPlaying(true);
      const onPause = () => setPlaying(false);
      const onEnded = () => setPlaying(false);
      const onTime = () => {
        const ms = audio.currentTime * 1000;
        setCurrentMs(ms);
        onTimeUpdate?.(ms);
      };
      const onLoaded = () => {
        if (isFinite(audio.duration) && audio.duration > 0) {
          setResolvedDurationMs(audio.duration * 1000);
        }
      };
      audio.addEventListener("play", onPlay);
      audio.addEventListener("pause", onPause);
      audio.addEventListener("ended", onEnded);
      audio.addEventListener("timeupdate", onTime);
      audio.addEventListener("loadedmetadata", onLoaded);
      return () => {
        audio.removeEventListener("play", onPlay);
        audio.removeEventListener("pause", onPause);
        audio.removeEventListener("ended", onEnded);
        audio.removeEventListener("timeupdate", onTime);
        audio.removeEventListener("loadedmetadata", onLoaded);
      };
    }, [onTimeUpdate]);

    const total = resolvedDurationMs ?? 0;
    const progressPct = total > 0 ? Math.min(100, (currentMs / total) * 100) : 0;

    const handleScrub = (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.currentTarget;
      const rect = target.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const audio = audioRef.current;
      if (!audio || !isFinite(audio.duration)) return;
      audio.currentTime = ratio * audio.duration;
    };

    return (
      <div className={cn("space-y-3", className)}>
        <audio ref={audioRef} src={src} preload="metadata" />
        <div className="flex items-center gap-4">
          <button
            type="button"
            aria-label={playing ? "Pause" : "Play"}
            onClick={handlePlay}
            className={cn(
              "shrink-0 w-10 h-10 rounded-full flex items-center justify-center",
              "border border-border bg-secondary/30 hover:bg-secondary/60 hover:border-accent-500/40 hover:text-accent-500 transition-colors",
              "text-cream",
            )}
          >
            {playing ? (
              <Pause className="w-4 h-4" strokeWidth={2} fill="currentColor" />
            ) : (
              <Play className="w-4 h-4 translate-x-px" strokeWidth={2} fill="currentColor" />
            )}
          </button>

          <div className="flex-1 flex items-center gap-3">
            <span className="font-mono text-[11px] tabular-figs text-cream-muted/70 shrink-0">
              {formatDuration(currentMs)}
            </span>
            <div
              role="slider"
              tabIndex={0}
              aria-label="Audio position"
              aria-valuemin={0}
              aria-valuemax={total}
              aria-valuenow={currentMs}
              className="flex-1 h-6 flex items-center cursor-pointer group"
              onClick={handleScrub}
            >
              <div className="w-full relative h-px bg-border">
                <div
                  className="absolute inset-y-0 left-0 bg-accent-500"
                  style={{ width: `${progressPct}%` }}
                />
                <div
                  aria-hidden
                  className={cn(
                    "absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-accent-500",
                    "opacity-0 group-hover:opacity-100 transition-opacity",
                  )}
                  style={{ left: `calc(${progressPct}% - 4px)` }}
                />
              </div>
            </div>
            <span className="font-mono text-[11px] tabular-figs text-cream-muted/70 shrink-0">
              {formatDuration(total)}
            </span>
          </div>
        </div>
      </div>
    );
  },
);
