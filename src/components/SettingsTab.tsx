import { useEffect, useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import {
  Mic,
  Cpu,
  FolderOpen,
  Trash2,
  Hand,
  ToggleRight,
  HardDrive,
  ExternalLink,
  Moon,
  Sparkles,
  Flame,
  Waves,
  Snowflake,
  Building2,
} from "lucide-react";
import { applyThemePalette, getPaletteMeta, THEME_PALETTES } from "@/lib/themes";
import { REWRITE_PRESET_OPTIONS } from "@/lib/constants";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
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
import { api } from "@/lib/api";
import type { Settings, Options, GpuInfo } from "@/lib/types";
import { ModelDownloadModal } from "./ModelDownloadModal";
import { HotkeyCapture } from "./HotkeyCapture";
import { LLMSettingsSection } from "./meetings/LLMSettingsSection";
import { MeetingsSettingsSection } from "./meetings/MeetingsSettingsSection";
import { cn } from "@/lib/utils";

// Hardcoded faster-whisper spec sheet. The backend exposes only model names,
// so size/VRAM/speed/accuracy live here as the source of truth for the picker.
type ModelMeta = {
  sizeMb: number;
  vram: string;
  speed: 1 | 2 | 3 | 4 | 5;
  accuracy: 1 | 2 | 3 | 4 | 5;
  tagline: string;
};

const MODEL_META: Record<string, ModelMeta> = {
  tiny:   { sizeMb: 75,   vram: "~1 GB",  speed: 5, accuracy: 1, tagline: "Fastest. Drafts and rough notes." },
  base:   { sizeMb: 142,  vram: "~1 GB",  speed: 5, accuracy: 2, tagline: "Light footprint. Casual dictation." },
  small:  { sizeMb: 466,  vram: "~2 GB",  speed: 4, accuracy: 3, tagline: "Balanced. Comfortable on CPU." },
  medium: { sizeMb: 1500, vram: "~5 GB",  speed: 2, accuracy: 4, tagline: "More accurate. Heavier on resources." },
  large:  { sizeMb: 2900, vram: "~10 GB", speed: 1, accuracy: 5, tagline: "Highest accuracy. Slowest." },
  turbo:  { sizeMb: 1600, vram: "~6 GB",  speed: 4, accuracy: 5, tagline: "Fast and accurate. Recommended for GPU." },
};

const FALLBACK_META: ModelMeta = {
  sizeMb: 0,
  vram: "—",
  speed: 3,
  accuracy: 3,
  tagline: "",
};

const THEME_ICONS: Record<string, React.ElementType> = {
  midnight: Moon,
  aurora: Sparkles,
  ember: Flame,
  ocean: Waves,
  snowfall: Snowflake,
  neonCity: Building2,
};

const SECTIONS = [
  { id: "transcription", num: "01", label: "transcription" },
  { id: "behavior",      num: "02", label: "behavior" },
  { id: "meetings",      num: "03", label: "meetings" },
  { id: "ai_summary",    num: "04", label: "ai summary" },
  { id: "appearance",    num: "05", label: "appearance" },
  { id: "data",          num: "06", label: "data" },
  { id: "reset",         num: "07", label: "reset" },
] as const;

function formatModelSize(mb: number): string {
  if (mb === 0) return "—";
  if (mb < 1000) return `${mb} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 MB";
  const mb = bytes / (1024 * 1024);
  if (mb < 1000) return `${mb.toFixed(0)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

function shortenGpuName(name: string): string {
  return name.replace("NVIDIA ", "").replace(" Laptop GPU", "");
}

export function SettingsTab() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [downloadModalOpen, setDownloadModalOpen] = useState(false);
  const [pendingModel, setPendingModel] = useState<string | null>(null);

  const [gpuInfo, setGpuInfo] = useState<GpuInfo | null>(null);
  const [deviceError, setDeviceError] = useState<string | null>(null);

  const [modelCacheDir, setModelCacheDir] = useState<string | null>(null);
  const [modelStatus, setModelStatus] = useState<Record<string, boolean>>({});

  // settingsRef lets stable callbacks read fresh state without re-creating on every settings change
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const [settingsData, optionsData, gpuData] = await Promise.all([
        api.getSettings(),
        api.getOptions(),
        api.getGpuInfo(),
      ]);
      setSettings(settingsData);
      setOptions(optionsData);
      setGpuInfo(gpuData);
    } catch (err) {
      console.error("Failed to load settings:", err);
      setError("Failed to load settings. Please try again.");
      toast.error("Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    api
      .getModelCacheDir()
      .then((res) => setModelCacheDir(res.path))
      .catch(() => setModelCacheDir(null));
  }, []);

  const refreshModelStatus = useCallback(async () => {
    if (!options) return;
    const results = await Promise.all(
      options.models.map(async (m) => {
        try {
          const info = await api.getModelInfo(m);
          return [m, info.cached] as const;
        } catch {
          return [m, false] as const;
        }
      })
    );
    setModelStatus(Object.fromEntries(results));
  }, [options]);

  useEffect(() => {
    refreshModelStatus();
  }, [refreshModelStatus]);

  const updateSetting = useCallback(
    async <K extends keyof Settings>(key: K, value: Settings[K]) => {
      const current = settingsRef.current;
      if (!current) return;
      const next = { ...current, [key]: value };
      setSettings(next);
      try {
        await api.updateSettings({ [key]: value });
        toast.success("Settings saved");
      } catch (err) {
        console.error("Failed to update setting:", err);
        toast.error("Failed to save settings");
        setSettings(current);
      }
    },
    []
  );

  const handleModelChange = useCallback(
    async (newModel: string) => {
      const current = settingsRef.current;
      if (!current) return;
      if (newModel === current.model) return;
      try {
        const modelInfo = await api.getModelInfo(newModel);
        if (modelInfo.cached) {
          updateSetting("model", newModel);
        } else {
          setPendingModel(newModel);
          setDownloadModalOpen(true);
        }
      } catch (err) {
        console.error("Failed to get model info:", err);
        toast.error("Failed to check model status");
      }
    },
    [updateSetting]
  );

  const handleDownloadComplete = useCallback(
    (success: boolean) => {
      if (success && pendingModel) {
        updateSetting("model", pendingModel);
        setModelStatus((prev) => ({ ...prev, [pendingModel]: true }));
      }
      setDownloadModalOpen(false);
      setPendingModel(null);
    },
    [pendingModel, updateSetting]
  );

  const handleDownloadCancel = useCallback(() => {
    setDownloadModalOpen(false);
    setPendingModel(null);
  }, []);

  const handleDeleteModel = useCallback(async (model: string) => {
    // Active model is guarded in the UI; this is belt-and-suspenders.
    if (model === settingsRef.current?.model) return;
    try {
      const res = await api.deleteModel(model);
      if (res.success) {
        setModelStatus((prev) => ({ ...prev, [model]: false }));
        toast.success(`Deleted ${model} — freed ${formatBytes(res.deleted_bytes)}`);
      } else {
        toast.error(res.error ?? "Failed to delete model");
      }
    } catch (err) {
      console.error("Failed to delete model:", err);
      toast.error("Failed to delete model");
    }
  }, []);

  const validateHotkey = useCallback(
    async (
      hotkey: string,
      excludeField: "holdHotkey" | "toggleHotkey"
    ): Promise<{ valid: boolean; error: string | null }> => {
      try {
        const result = await api.validateHotkey(hotkey, excludeField);
        return { valid: result.valid, error: result.error };
      } catch {
        return { valid: false, error: "Failed to validate hotkey" };
      }
    },
    []
  );

  const handleDeviceChange = useCallback(async (newDevice: string) => {
    const current = settingsRef.current;
    if (!current) return;
    setDeviceError(null);
    const validation = await api.validateDevice(newDevice);
    if (!validation.valid) {
      setDeviceError(validation.error);
      toast.error(validation.error || "Invalid device selection");
      return;
    }
    setSettings({ ...current, device: newDevice });
    try {
      await api.updateSettings({ device: newDevice });
      const gpuData = await api.getGpuInfo();
      setGpuInfo(gpuData);
      toast.success("Device updated — model will reload");
    } catch (err) {
      console.error("Failed to update device:", err);
      toast.error("Failed to update device");
      setSettings(current);
    }
  }, []);

  useEffect(() => {
    if (!settings) return;
    applyThemePalette(settings.theme);
  }, [settings?.theme]);

  if (loading) return <LoadingState />;
  if (error || !settings || !options) {
    return <ErrorState error={error} onRetry={loadSettings} />;
  }

  return (
    <div className="min-h-full w-full bg-background">
      <div className="w-full max-w-4xl mx-auto px-6 md:px-10 py-10 md:py-16 space-y-16">
        <header className="space-y-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
            ~/dictore/preferences
          </p>
          <h1 className="font-display text-4xl md:text-5xl font-medium tracking-tight text-cream leading-[1.05]">
            Settings
          </h1>
          <p className="text-sm text-cream-muted max-w-xl leading-relaxed">
            Local-first by design. Every preference here lives on your machine in{" "}
            <span className="font-mono text-cream">~/.Dictore/</span>. Changes
            save as you go.
          </p>
          <SectionIndex />
        </header>

        <Section
          id="transcription"
          index="01"
          title="Transcription"
          description="The pipeline that turns your voice into text — model, language, microphone, compute."
        >
          <SectionBlock
            label="Model"
            helper="Larger models are more accurate but slower and use more memory. Models download on first use."
          >
            <ModelPicker
              models={options.models}
              currentModel={settings.model}
              statuses={modelStatus}
              onChange={handleModelChange}
              onDelete={handleDeleteModel}
            />
          </SectionBlock>

          <SettingRow label="Language" helper="Auto-detect works for most cases.">
            <SelectField
              value={settings.language}
              onChange={(v) => updateSetting("language", v)}
              options={options.languages.map((l) => ({
                value: l,
                label: l === "auto" ? "Auto-detect" : l.toUpperCase(),
              }))}
            />
          </SettingRow>

          <SettingRow
            label="Microphone"
            helper="Audio capture device. Defaults to your system input."
          >
            <SelectField
              value={String(settings.microphone)}
              onChange={(v) => updateSetting("microphone", Number(v))}
              options={[
                { value: "-1", label: "System default" },
                ...options.microphones.map((m) => ({
                  value: String(m.id),
                  label: m.name,
                })),
              ]}
              icon={Mic}
            />
          </SettingRow>

          <SectionBlock
            label="Compute device"
            helper="CPU is reliable everywhere. CUDA needs an NVIDIA GPU and cuDNN 9.x."
          >
            <ComputePanel
              value={settings.device}
              gpuInfo={gpuInfo}
              error={deviceError}
              options={options.deviceOptions}
              onChange={handleDeviceChange}
            />
          </SectionBlock>
        </Section>

        <Section
          id="behavior"
          index="02"
          title="Behavior"
          description="How Dictore reacts when you speak — hotkeys, indicators, and small touches."
        >
          <SectionBlock
            label="Hotkeys"
            helper="Bind a global hold or toggle shortcut. Use either, both, or neither."
          >
            <HotkeysPanel
              settings={settings}
              onUpdate={updateSetting}
              onValidate={validateHotkey}
            />
          </SectionBlock>

          <ToggleRow
            label="Auto-rewrite"
            helper="Polish transcribed text with a preset before pasting — same presets as VoiceKey on iOS."
            checked={settings.autoRewriteEnabled ?? true}
            onChange={(v) => updateSetting("autoRewriteEnabled", v)}
          />
          <SettingRow label="Rewrite preset" helper="How dictated text is cleaned up before paste.">
            <SelectField
              value={settings.rewritePreset ?? "grammar_correct"}
              onChange={(v) => updateSetting("rewritePreset", v as Settings["rewritePreset"])}
              options={REWRITE_PRESET_OPTIONS.map((p) => ({
                value: p.val,
                label: p.label,
              }))}
            />
          </SettingRow>
          <ToggleRow
            label="Remove filler words"
            helper="Strips um, uh, like, and other verbal tics from transcriptions."
            checked={settings.fillerRemovalEnabled ?? true}
            onChange={(v) => updateSetting("fillerRemovalEnabled", v)}
          />
          <ToggleRow
            label="Floating recording indicator"
            helper="Shows a small pill at the bottom of your screen while recording. Hide it for a quieter experience — recording still works."
            checked={settings.showPopup}
            onChange={(v) => updateSetting("showPopup", v)}
          />
          <ToggleRow
            label="Save dictation audio"
            helper="Keep the original audio with each transcription so you can play it back. Stays on your device."
            checked={settings.saveAudioToHistory}
            onChange={(v) => updateSetting("saveAudioToHistory", v)}
          />
          <ToggleRow
            label="Prepend space"
            helper="Adds a leading space before pasted text. Prevents sentences from running together when you dictate continuously."
            checked={settings.prependSpace}
            onChange={(v) => updateSetting("prependSpace", v)}
          />
          <ToggleRow
            label="Launch at login"
            helper="Start Dictore when you sign in to your computer."
            checked={settings.autoStart}
            onChange={(v) => updateSetting("autoStart", v)}
          />
        </Section>

        <Section
          id="meetings"
          index="03"
          title="Meetings"
          description="Long-form recording, transcription, and review. Captures your microphone, the other side of a Teams/Meet/Zoom call, or both."
        >
          <MeetingsSettingsSection />
        </Section>

        <Section
          id="ai_summary"
          index="04"
          title="AI summary"
          description="The model that turns a transcript into a structured summary. Use a local Ollama instance for full privacy, or any OpenAI-compatible cloud provider."
        >
          <LLMSettingsSection />
        </Section>

        <Section
          id="appearance"
          index="05"
          title="Appearance"
          description="Six color palettes from VoiceKey — Midnight is the default."
        >
          <ThemePicker
            value={settings.theme}
            onChange={(v) => updateSetting("theme", v as Settings["theme"])}
          />
        </Section>

        <Section
          id="data"
          index="06"
          title="Data"
          description="What gets kept, where it lives, and for how long."
        >
          <SectionBlock
            label="Retention"
            helper="History entries older than this are automatically removed."
          >
            <Segmented
              value={String(settings.retention)}
              options={Object.entries(options.retentionOptions).map(
                ([label, days]) => ({ value: String(days), label })
              )}
              onChange={(v) => updateSetting("retention", Number(v))}
            />
          </SectionBlock>

          <SectionBlock label="Storage paths" helper="Files Dictore keeps on disk.">
            <StoragePaths modelCacheDir={modelCacheDir} />
          </SectionBlock>
        </Section>

        <Section
          id="reset"
          index="07"
          title="Reset"
          tone="danger"
          description="Wipe local state and start over. None of this can be undone."
        >
          <DangerZone onModelsCleared={refreshModelStatus} />
        </Section>

        <footer className="pt-8 border-t border-border flex items-center justify-between font-mono text-[11px] text-cream-muted/60">
          <span>Dictore · local · open-source</span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-500" />
            preferences saved
          </span>
        </footer>
      </div>

      {pendingModel && (
        <ModelDownloadModal
          open={downloadModalOpen}
          modelName={pendingModel}
          onComplete={handleDownloadComplete}
          onCancel={handleDownloadCancel}
        />
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="min-h-screen w-full bg-background flex items-center justify-center px-6">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 rounded-full border-2 border-accent-500/30 border-t-accent-500 animate-spin" />
        <p className="font-mono text-[11px] text-cream-muted/60 uppercase tracking-widest">
          loading preferences…
        </p>
      </div>
    </div>
  );
}

function ErrorState({
  error,
  onRetry,
}: {
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <div className="min-h-screen w-full bg-background flex items-center justify-center px-6">
      <div className="text-center space-y-4 max-w-sm">
        <p className="font-mono text-[11px] uppercase tracking-widest text-destructive">
          read failed
        </p>
        <p className="text-cream">{error || "Failed to load settings"}</p>
        <Button type="button" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    </div>
  );
}

function SectionIndex() {
  const handleClick = (id: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  return (
    <nav
      aria-label="Settings sections"
      className="flex flex-wrap gap-x-4 gap-y-2 font-mono text-[11px] pt-2"
    >
      {SECTIONS.map((s, i) => (
        <span key={s.id} className="flex items-center gap-4">
          {i > 0 && <span className="text-cream-muted/30">/</span>}
          <button
            type="button"
            onClick={handleClick(s.id)}
            className="text-cream-muted/60 hover:text-accent-500 transition-colors"
          >
            <span className="text-cream-muted/40">{s.num}</span>{" "}
            <span className="uppercase tracking-widest">{s.label}</span>
          </button>
        </span>
      ))}
    </nav>
  );
}

function Section({
  id,
  index,
  title,
  description,
  tone = "default",
  children,
}: {
  id: string;
  index: string;
  title: string;
  description?: string;
  tone?: "default" | "danger";
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-8 space-y-8">
      <div className="space-y-2">
        <p
          className={cn(
            "font-mono text-[10px] uppercase tracking-[0.25em]",
            tone === "danger" ? "text-destructive/80" : "text-cream-muted/60"
          )}
        >
          {index} / {title}
        </p>
        <h2
          className={cn(
            "font-display text-2xl md:text-3xl font-medium tracking-tight leading-tight",
            tone === "danger" ? "text-destructive" : "text-cream"
          )}
        >
          {title}
        </h2>
        {description && (
          <p className="text-sm text-cream-muted max-w-2xl leading-relaxed">
            {description}
          </p>
        )}
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function SectionBlock({
  label,
  helper,
  children,
}: {
  label?: string;
  helper?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="py-5 border-t border-border first:border-t-0 space-y-3">
      {(label || helper) && (
        <div className="space-y-1">
          {label && <p className="text-sm font-medium text-cream">{label}</p>}
          {helper && (
            <p className="text-xs text-cream-muted leading-relaxed max-w-2xl">
              {helper}
            </p>
          )}
        </div>
      )}
      <div>{children}</div>
    </div>
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
    <div className="py-5 border-t border-border first:border-t-0 flex flex-col gap-3 md:flex-row md:items-center md:justify-between md:gap-8">
      <div className="md:max-w-md">
        <p className="text-sm font-medium text-cream">{label}</p>
        {helper && (
          <p className="text-xs text-cream-muted mt-1 leading-relaxed">
            {helper}
          </p>
        )}
      </div>
      <div className="md:flex-shrink-0 md:w-72">{children}</div>
    </div>
  );
}

function ToggleRow({
  label,
  helper,
  checked,
  onChange,
}: {
  label: string;
  helper?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  const id = `toggle-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="py-4 border-t border-border first:border-t-0 flex items-start justify-between gap-6">
      <div className="flex-1 min-w-0">
        <Label
          htmlFor={id}
          className="text-sm font-medium text-cream cursor-pointer"
        >
          {label}
        </Label>
        {helper && (
          <p className="text-xs text-cream-muted mt-1 leading-relaxed max-w-2xl">
            {helper}
          </p>
        )}
      </div>
      <Switch
        id={id}
        checked={checked}
        onCheckedChange={onChange}
        className="mt-0.5 flex-shrink-0"
      />
    </div>
  );
}

function SelectField({
  value,
  onChange,
  options,
  icon: Icon,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  icon?: React.ElementType;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-10 rounded-md font-mono text-sm bg-secondary/40 border-border hover:bg-secondary/60 transition-colors">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-3.5 h-3.5 text-cream-muted/70" />}
          <SelectValue />
        </div>
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem
            key={o.value}
            value={o.value}
            className="font-mono text-sm"
          >
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function ModelPicker({
  models,
  currentModel,
  statuses,
  onChange,
  onDelete,
}: {
  models: string[];
  currentModel: string;
  statuses: Record<string, boolean>;
  onChange: (m: string) => void;
  onDelete: (m: string) => void;
}) {
  return (
    <div className="border border-border rounded-md overflow-hidden bg-surface">
      {models.map((model, i) => {
        const meta = MODEL_META[model] ?? FALLBACK_META;
        const cached = statuses[model];
        const isActive = model === currentModel;
        const cacheState =
          cached === undefined ? "unknown" : cached ? "cached" : "absent";
        const canDelete = cacheState === "cached" && !isActive;
        return (
          <div
            key={model}
            className={cn(
              "transition-colors flex items-stretch group",
              i > 0 && "border-t border-border",
              isActive ? "bg-accent-500/[0.04]" : "hover:bg-secondary/40"
            )}
          >
            <div
              className={cn(
                "w-1 flex-shrink-0 transition-colors",
                isActive ? "bg-accent-500" : "bg-transparent"
              )}
              aria-hidden
            />
            <button
              type="button"
              onClick={() => onChange(model)}
              aria-pressed={isActive}
              className="flex-1 text-left flex items-center gap-4 pl-5 pr-3 py-4 min-w-0"
            >
              <ModelStatusDot active={isActive} cached={cacheState} />
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-3 flex-wrap">
                  <span className="font-display text-base font-medium tracking-tight text-cream">
                    {model}
                  </span>
                  {cacheState === "absent" && (
                    <span className="font-mono text-[10px] uppercase tracking-widest text-cream-muted/60">
                      ↓ download required
                    </span>
                  )}
                  {isActive && (
                    <span className="font-mono text-[10px] uppercase tracking-widest text-accent-500">
                      active
                    </span>
                  )}
                </div>
                <p className="text-xs text-cream-muted mt-1 truncate">
                  {meta.tagline}
                </p>
              </div>
              <div className="hidden sm:flex items-center gap-6 flex-shrink-0">
                <ModelMetaCol label="size" value={formatModelSize(meta.sizeMb)} />
                <ModelMetaCol label="vram" value={meta.vram} />
                <DotMeter label="speed" value={meta.speed} />
                <DotMeter label="accuracy" value={meta.accuracy} />
              </div>
            </button>
            {canDelete && <ModelDeleteButton model={model} onDelete={onDelete} />}
          </div>
        );
      })}
    </div>
  );
}

function ModelDeleteButton({
  model,
  onDelete,
}: {
  model: string;
  onDelete: (m: string) => void;
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <button
          type="button"
          className="flex-shrink-0 self-stretch px-4 flex items-center text-cream-muted/40 hover:text-destructive hover:bg-destructive/[0.06] transition-colors"
          aria-label={`Delete ${model}`}
          title={`Delete ${model} from disk`}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="font-display">
            Delete {model}?
          </AlertDialogTitle>
          <AlertDialogDescription>
            Removes the downloaded model from disk to free up space. You can
            re-download it anytime by selecting it again.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => onDelete(model)}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ModelStatusDot({
  active,
  cached,
}: {
  active: boolean;
  cached: "cached" | "absent" | "unknown";
}) {
  if (active) {
    return (
      <span
        className="relative flex-shrink-0 inline-flex items-center justify-center w-3 h-3"
        aria-hidden
      >
        <span className="absolute inset-0 rounded-full bg-accent-500" />
        <span className="absolute inset-0 rounded-full bg-accent-500 animate-ping opacity-40" />
      </span>
    );
  }
  if (cached === "cached") {
    return (
      <span
        className="w-3 h-3 rounded-full border border-cream-muted/40 flex-shrink-0"
        aria-hidden
      />
    );
  }
  if (cached === "absent") {
    return (
      <span
        className="w-3 h-3 rounded-full border border-dashed border-cream-muted/30 flex-shrink-0"
        aria-hidden
      />
    );
  }
  return <span className="w-3 h-3 flex-shrink-0" aria-hidden />;
}

function ModelMetaCol({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col items-end gap-1 min-w-[64px]">
      <span className="font-mono text-[9px] uppercase tracking-widest text-cream-muted/50">
        {label}
      </span>
      <span className="font-mono text-[11px] text-cream-muted">{value}</span>
    </div>
  );
}

function DotMeter({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-end gap-1 min-w-[60px]">
      <span className="font-mono text-[9px] uppercase tracking-widest text-cream-muted/50">
        {label}
      </span>
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <span
            key={i}
            className={cn(
              "w-1 h-1 rounded-full",
              i <= value ? "bg-accent-500" : "bg-cream-muted/20"
            )}
          />
        ))}
      </div>
    </div>
  );
}

function ComputePanel({
  value,
  gpuInfo,
  error,
  options,
  onChange,
}: {
  value: string;
  gpuInfo: GpuInfo | null;
  error: string | null;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {options.map((d) => {
          const isActive = value === d;
          const disabled = d === "cuda" && !gpuInfo?.cudaAvailable;
          const label = d === "auto" ? "Auto" : d === "cuda" ? "CUDA" : "CPU";
          return (
            <button
              key={d}
              type="button"
              onClick={() => !disabled && onChange(d)}
              disabled={disabled}
              aria-pressed={isActive}
              className={cn(
                "h-9 px-4 rounded-md border font-mono text-xs uppercase tracking-widest transition-colors",
                isActive
                  ? "bg-accent-500/10 border-accent-500/40 text-accent-500"
                  : disabled
                    ? "bg-secondary/20 border-border text-cream-muted/30 cursor-not-allowed"
                    : "bg-secondary/30 border-border text-cream-muted hover:bg-secondary/60 hover:text-cream"
              )}
            >
              {label}
              {d === "cuda" && !gpuInfo?.cudaAvailable && (
                <span className="ml-2 normal-case tracking-normal text-cream-muted/40">
                  unavailable
                </span>
              )}
            </button>
          );
        })}
      </div>
      {error && (
        <p className="font-mono text-[11px] text-destructive">{error}</p>
      )}
      {gpuInfo && (
        <dl className="font-mono text-[12px] grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 pt-2">
          <dt className="text-cream-muted/60 uppercase tracking-widest text-[10px] self-center">
            status
          </dt>
          <dd
            className={cn(
              gpuInfo.cudaAvailable
                ? "text-accent-500"
                : gpuInfo.gpuName && !gpuInfo.cudnnAvailable
                  ? "text-amber-500"
                  : "text-cream-muted"
            )}
          >
            {gpuInfo.cudaAvailable
              ? "cuda available"
              : gpuInfo.gpuName && !gpuInfo.cudnnAvailable
                ? "cudnn missing"
                : "cpu only"}
          </dd>
          {gpuInfo.gpuName && (
            <>
              <dt className="text-cream-muted/60 uppercase tracking-widest text-[10px] self-center">
                gpu
              </dt>
              <dd className="text-cream truncate" title={gpuInfo.gpuName}>
                {shortenGpuName(gpuInfo.gpuName)}
              </dd>
            </>
          )}
          <dt className="text-cream-muted/60 uppercase tracking-widest text-[10px] self-center">
            active
          </dt>
          <dd className="text-cream">
            {gpuInfo.currentDevice} · {gpuInfo.currentComputeType}
          </dd>
        </dl>
      )}
      {gpuInfo?.gpuName && !gpuInfo.cudnnAvailable && (
        <p className="font-mono text-[11px] text-amber-500/90 border-l-2 border-amber-500/40 pl-3 py-1">
          install cudnn 9.x to enable gpu acceleration
        </p>
      )}
    </div>
  );
}

function HotkeysPanel({
  settings,
  onUpdate,
  onValidate,
}: {
  settings: Settings;
  onUpdate: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  onValidate: (
    hotkey: string,
    exclude: "holdHotkey" | "toggleHotkey"
  ) => Promise<{ valid: boolean; error: string | null }>;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <HotkeyMode
        icon={Hand}
        title="Hold mode"
        description="Hold to record, release to stop."
        enabled={settings.holdHotkeyEnabled}
        hotkey={settings.holdHotkey}
        onToggle={(v) => onUpdate("holdHotkeyEnabled", v)}
        onChange={(h) => onUpdate("holdHotkey", h)}
        onValidate={(h) => onValidate(h, "holdHotkey")}
      />
      <HotkeyMode
        icon={ToggleRight}
        title="Toggle mode"
        description="Press once to start, again to stop."
        enabled={settings.toggleHotkeyEnabled}
        hotkey={settings.toggleHotkey}
        onToggle={(v) => onUpdate("toggleHotkeyEnabled", v)}
        onChange={(h) => onUpdate("toggleHotkey", h)}
        onValidate={(h) => onValidate(h, "toggleHotkey")}
      />
    </div>
  );
}

function HotkeyMode({
  icon: Icon,
  title,
  description,
  enabled,
  hotkey,
  onToggle,
  onChange,
  onValidate,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  enabled: boolean;
  hotkey: string;
  onToggle: (v: boolean) => void;
  onChange: (h: string) => void;
  onValidate: (h: string) => Promise<{ valid: boolean; error: string | null }>;
}) {
  return (
    <div
      className={cn(
        "panel p-5 space-y-4 transition-opacity",
        !enabled && "opacity-60"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Icon
            className={cn(
              "w-4 h-4 mt-0.5 flex-shrink-0",
              enabled ? "text-accent-500" : "text-cream-muted/50"
            )}
            strokeWidth={2}
          />
          <div>
            <h4 className="text-sm font-medium text-cream">{title}</h4>
            <p className="text-xs text-cream-muted mt-0.5 leading-relaxed">
              {description}
            </p>
          </div>
        </div>
        <Switch checked={enabled} onCheckedChange={onToggle} />
      </div>
      <HotkeyCapture
        value={hotkey}
        onChange={onChange}
        onValidate={onValidate}
        disabled={!enabled}
      />
    </div>
  );
}

function ThemePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-w-2xl">
      {THEME_PALETTES.map((palette) => {
        const Icon = THEME_ICONS[palette.id] ?? Moon;
        const isActive = value === palette.id || getPaletteMeta(value).id === palette.id;
        return (
          <button
            key={palette.id}
            type="button"
            onClick={() => onChange(palette.id)}
            aria-pressed={isActive}
            className={cn(
              "relative flex flex-col items-start gap-3 rounded-xl border p-4 transition-all text-left",
              isActive
                ? "border-accent-500/50 bg-accent-500/5 ring-1 ring-accent-500/30"
                : "border-border bg-secondary/20 hover:bg-secondary/40"
            )}
          >
            <div
              className="w-full h-10 rounded-lg"
              style={{
                background: `linear-gradient(135deg, ${palette.accent}, ${palette.accentEnd})`,
              }}
              aria-hidden
            />
            <div className="flex items-center gap-2 w-full">
              <Icon
                className={cn(
                  "w-4 h-4",
                  isActive ? "text-accent-500" : "text-cream-muted/70"
                )}
                strokeWidth={2}
              />
              <span className="text-sm font-medium text-cream">{palette.name}</span>
            </div>
            {isActive && (
              <span className="absolute top-3 right-3 w-2 h-2 rounded-full bg-accent-500" aria-hidden />
            )}
          </button>
        );
      })}
    </div>
  );
}

function Segmented({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="inline-flex flex-wrap gap-1 p-1 rounded-md border border-border bg-secondary/30">
      {options.map((o) => {
        const isActive = value === o.value;
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            aria-pressed={isActive}
            className={cn(
              "h-8 px-3 rounded text-xs font-mono uppercase tracking-widest transition-colors",
              isActive
                ? "bg-background text-cream shadow-sm"
                : "text-cream-muted hover:text-cream"
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function StoragePaths({ modelCacheDir }: { modelCacheDir: string | null }) {
  return (
    <div className="border border-border rounded-md divide-y divide-border bg-surface">
      <PathRow
        label="App data"
        description="History, settings, audio recordings"
        path="~/.Dictore/"
        onOpen={() => api.openDataFolder()}
      />
      <PathRow
        label="Model cache"
        description="Downloaded Whisper models (Hugging Face)"
        path={modelCacheDir ?? "Resolving…"}
        onOpen={() => api.openModelCacheDir()}
        disabled={!modelCacheDir}
      />
    </div>
  );
}

function PathRow({
  label,
  description,
  path,
  onOpen,
  disabled,
}: {
  label: string;
  description: string;
  path: string;
  onOpen: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-4 px-5 py-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-medium text-cream">{label}</span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-cream-muted/60">
            {description}
          </span>
        </div>
        <code
          className="font-mono text-[11px] text-cream-muted mt-1.5 block break-all"
          title={path}
        >
          {path}
        </code>
      </div>
      <button
        type="button"
        onClick={onOpen}
        disabled={disabled}
        className="flex-shrink-0 h-9 px-3 rounded-md border border-border bg-secondary/40 hover:bg-secondary/60 hover:border-accent-500/30 hover:text-accent-500 transition-colors flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-cream-muted disabled:opacity-40 disabled:cursor-not-allowed"
        aria-label={`Open ${label}`}
      >
        <ExternalLink className="w-3.5 h-3.5" />
        open
      </button>
    </div>
  );
}

function DangerZone({ onModelsCleared }: { onModelsCleared: () => void }) {
  const [deleteAppData, setDeleteAppData] = useState(true);
  const [deleteModels, setDeleteModels] = useState(false);
  const [deleteCudaLibs, setDeleteCudaLibs] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      if (deleteAppData) await api.resetAllData();
      if (deleteModels) await api.clearModelCache();
      if (deleteCudaLibs) await api.clearCudaLibs();

      const parts: string[] = [];
      if (deleteAppData) parts.push("app data");
      if (deleteModels) parts.push("models");
      if (deleteCudaLibs) parts.push("CUDA libraries");
      const message =
        parts.length > 0 ? `Deleted: ${parts.join(", ")}` : "Nothing deleted";

      // Resetting app data wipes settings/onboarding, so we must return to
      // setup. Deleting only models/CUDA leaves the app usable — stay put.
      if (deleteAppData) {
        toast.success(`${message} — returning to setup`);
        setTimeout(() => {
          window.location.hash = "/onboarding";
          window.location.reload();
        }, 500);
      } else {
        toast.success(message);
        if (deleteModels) onModelsCleared();
      }
    } catch (err) {
      console.error("Failed to delete data:", err);
      toast.error("Failed to delete data");
    } finally {
      setIsDeleting(false);
    }
  };

  const canDelete = deleteAppData || deleteModels || deleteCudaLibs;

  return (
    <div className="border border-destructive/20 rounded-md bg-destructive/[0.03] p-6 space-y-5">
      <div className="flex items-start gap-3">
        <Trash2
          className="w-4 h-4 text-destructive mt-0.5 flex-shrink-0"
          strokeWidth={2}
        />
        <div className="flex-1">
          <p className="text-sm font-medium text-cream">Reset all data</p>
          <p className="text-xs text-cream-muted mt-1 leading-relaxed max-w-xl">
            Choose what to delete. After confirming, Dictore returns to
            onboarding so you can set things up fresh.
          </p>
        </div>
      </div>

      <AlertDialog>
        <AlertDialogTrigger asChild>
          <button
            type="button"
            className="h-10 px-5 rounded-md border border-destructive/40 bg-transparent text-destructive font-mono text-xs uppercase tracking-widest hover:bg-destructive hover:text-destructive-foreground transition-colors flex items-center gap-2"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Choose what to reset
          </button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display">
              What would you like to delete?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Select what to remove. These actions cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="space-y-2 py-2">
            <DeleteOption
              icon={FolderOpen}
              checked={deleteAppData}
              onCheckedChange={setDeleteAppData}
              title="App data"
              description="History, settings, audio recordings"
            />
            <DeleteOption
              icon={HardDrive}
              checked={deleteModels}
              onCheckedChange={setDeleteModels}
              title="AI models"
              description="Whisper models — re-download required"
            />
            <DeleteOption
              icon={Cpu}
              checked={deleteCudaLibs}
              onCheckedChange={setDeleteCudaLibs}
              title="CUDA libraries"
              description="cuDNN + cuBLAS — re-download required"
            />
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={!canDelete || isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
            >
              {isDeleting ? "Deleting…" : "Delete selected"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function DeleteOption({
  icon: Icon,
  checked,
  onCheckedChange,
  title,
  description,
}: {
  icon: React.ElementType;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  title: string;
  description: string;
}) {
  return (
    <label className="flex items-start gap-3 p-3 rounded-md border border-border hover:bg-secondary/30 transition-colors cursor-pointer">
      <Checkbox
        checked={checked}
        onCheckedChange={(v) => onCheckedChange(v === true)}
        className="mt-0.5"
      />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <Icon
            className="w-3.5 h-3.5 text-cream-muted/60"
            strokeWidth={2}
          />
          <span className="text-sm font-medium text-cream">{title}</span>
        </div>
        <p className="text-xs text-cream-muted mt-1">{description}</p>
      </div>
    </label>
  );
}
