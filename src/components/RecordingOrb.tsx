import { cn } from "@/lib/utils";

interface RecordingOrbProps {
  isRecording: boolean;
  isActive?: boolean;
  amplitude?: number;
  onClick?: () => void;
  disabled?: boolean;
  size?: "sm" | "md" | "lg";
}

const SIZE_MAP = {
  sm: "w-24 h-24",
  md: "w-36 h-36 md:w-44 md:h-44",
  lg: "w-48 h-48 md:w-56 md:h-56",
};

export function RecordingOrb({
  isRecording,
  isActive = false,
  amplitude = 0,
  onClick,
  disabled = false,
  size = "lg",
}: RecordingOrbProps) {
  const scale = 1 + Math.min(amplitude, 1) * 0.12;
  const pulse = isRecording || isActive;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={isRecording}
      aria-label={isRecording ? "Stop recording" : "Start recording"}
      className={cn(
        "relative rounded-full transition-transform duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-60 disabled:cursor-not-allowed",
        SIZE_MAP[size]
      )}
      style={{ transform: pulse ? `scale(${scale})` : undefined }}
    >
      {/* Outer glow ring */}
      <span
        className={cn(
          "absolute inset-0 rounded-full recording-orb transition-all duration-300",
          pulse && "recording-orb-active"
        )}
        aria-hidden
      />

      {/* Inner highlight */}
      <span
        className="absolute inset-[18%] rounded-full bg-white/10 backdrop-blur-sm"
        aria-hidden
      />

      {/* Center dot / REC indicator */}
      <span className="absolute inset-0 flex items-center justify-center">
        {isRecording ? (
          <span className="relative flex items-center justify-center">
            <span className="w-3 h-3 rounded-sm bg-white/90" />
          </span>
        ) : (
          <span className="w-4 h-4 rounded-full bg-white/80" />
        )}
      </span>

      {/* Waveform ring when recording */}
      {isRecording && (
        <span
          className="absolute inset-[-8%] rounded-full border-2 border-recording-active/40 animate-ping"
          style={{ animationDuration: "2s" }}
          aria-hidden
        />
      )}
    </button>
  );
}

interface MiniWaveformProps {
  isActive: boolean;
  barCount?: number;
}

export function MiniWaveform({ isActive, barCount = 5 }: MiniWaveformProps) {
  return (
    <div className="flex items-end justify-center gap-0.5 h-5" aria-hidden>
      {Array.from({ length: barCount }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "w-0.5 rounded-full bg-current transition-all",
            isActive ? "waveform-bar" : "h-1 opacity-40"
          )}
          style={
            isActive
              ? {
                  height: `${8 + (i % 3) * 6}px`,
                  animationDelay: `${i * 0.12}s`,
                  backgroundColor: "var(--waveform-primary)",
                }
              : { height: "4px" }
          }
        />
      ))}
    </div>
  );
}
