import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Globe,
  Mic,
  Cpu,
  Zap,
  Clock,
  Palette,
  FolderOpen,
  Trash2,
  FileAudio,
  Keyboard,
  Hand,
  ToggleRight,
  HardDrive,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Settings, Options, GpuInfo } from "@/lib/types";
import { ModelDownloadModal } from "./ModelDownloadModal";
import { HotkeyCapture } from "./HotkeyCapture";
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
import { cn } from "@/lib/utils";

export function SettingsTab() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Model download modal state
  const [downloadModalOpen, setDownloadModalOpen] = useState(false);
  const [pendingModel, setPendingModel] = useState<string | null>(null);

  // GPU info state
  const [gpuInfo, setGpuInfo] = useState<GpuInfo | null>(null);
  const [deviceError, setDeviceError] = useState<string | null>(null);

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
    } catch (error) {
      console.error("Failed to load settings:", error);
      setError("Failed to load settings. Please try again.");
      toast.error("Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const updateSetting = async <K extends keyof Settings>(
    key: K,
    value: Settings[K]
  ) => {
    if (!settings) return;

    const newSettings = { ...settings, [key]: value };
    setSettings(newSettings);

    try {
      await api.updateSettings({ [key]: value });
      toast.success("Settings saved");
    } catch (error) {
      console.error("Failed to update setting:", error);
      toast.error("Failed to save settings");
      setSettings(settings); // Revert
    }
  };

  // Handle model change - check if download needed
  const handleModelChange = useCallback(
    async (newModel: string) => {
      if (!settings) return;

      try {
        const modelInfo = await api.getModelInfo(newModel);

        if (modelInfo.cached) {
          // Model is cached, just update settings
          updateSetting("model", newModel);
        } else {
          // Model needs download - show modal
          setPendingModel(newModel);
          setDownloadModalOpen(true);
        }
      } catch (err) {
        console.error("Failed to get model info:", err);
        toast.error("Failed to check model status");
      }
    },
    [settings]
  );

  // Handle download complete
  const handleDownloadComplete = useCallback(
    (success: boolean) => {
      if (success && pendingModel) {
        // Download succeeded, update settings
        updateSetting("model", pendingModel);
      }
      setDownloadModalOpen(false);
      setPendingModel(null);
    },
    [pendingModel]
  );

  // Handle download cancel
  const handleDownloadCancel = useCallback(() => {
    setDownloadModalOpen(false);
    setPendingModel(null);
    // Settings remain unchanged - dropdown still shows original model
  }, []);

  // Hotkey validation
  const validateHotkey = useCallback(
    async (hotkey: string, excludeField: "holdHotkey" | "toggleHotkey") => {
      try {
        const result = await api.validateHotkey(hotkey, excludeField);
        return { valid: result.valid, error: result.error };
      } catch (err) {
        return { valid: false, error: "Failed to validate hotkey" };
      }
    },
    []
  );

  // Handle device change with validation
  const handleDeviceChange = useCallback(
    async (newDevice: string) => {
      if (!settings) return;

      setDeviceError(null);

      // Validate the device selection
      const validation = await api.validateDevice(newDevice);
      if (!validation.valid) {
        setDeviceError(validation.error);
        toast.error(validation.error || "Invalid device selection");
        return;
      }

      // Update the setting
      const newSettings = { ...settings, device: newDevice };
      setSettings(newSettings);

      try {
        await api.updateSettings({ device: newDevice });
        // Refresh GPU info after device change
        const gpuData = await api.getGpuInfo();
        setGpuInfo(gpuData);
        toast.success("Device updated - model will reload");
      } catch (err) {
        console.error("Failed to update device:", err);
        toast.error("Failed to update device");
        setSettings(settings); // Revert
      }
    },
    [settings]
  );

  useEffect(() => {
    if (!settings) return;
    const root = document.documentElement;
    let isDark = false;
    if (settings.theme === "system") {
      isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    } else {
      isDark = settings.theme === "dark";
    }
    if (isDark) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [settings?.theme]);

  if (loading) {
    return (
      <div className="min-h-screen w-full bg-background/50 p-6 md:p-10 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-muted-foreground animate-pulse">
            Loading preferences...
          </p>
        </div>
      </div>
    );
  }

  if (error || !settings || !options) {
    return (
      <div className="min-h-screen w-full bg-background/50 p-6 md:p-10 flex items-center justify-center">
        <div className="text-center py-20 px-10 glass-card space-y-4">
          <p className="text-destructive font-medium text-lg">
            {error || "Failed to load settings"}
          </p>
          <button
            className="px-6 py-2.5 text-sm font-medium rounded-xl bg-background border border-border shadow-sm hover:bg-secondary/50 transition-all"
            onClick={loadSettings}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  const retentionEntries = Object.entries(options.retentionOptions);

  return (
    <div className="min-h-screen w-full bg-background/50 relative overflow-x-hidden">
      {/* Background effects */}
      <div className="fixed inset-0 bg-grid opacity-20 pointer-events-none overflow-hidden" />
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="orb orb-primary w-[400px] h-[400px] absolute -top-40 -right-40 opacity-20" />
        <div className="orb orb-accent w-[300px] h-[300px] absolute bottom-20 -left-20 opacity-15" />
      </div>

      <div className="w-full max-w-[1600px] mx-auto p-6 md:p-10 space-y-10 relative z-10">
        {/* Header */}
        <div className="flex flex-col gap-2">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tighter text-foreground">
            Sett<span className="headline-serif text-primary">ings</span>
          </h1>
          <p className="text-lg text-muted-foreground/80 font-light max-w-2xl">
            Customize your voice experience. All preferences are saved locally.
          </p>
        </div>

        {/* Divider */}
        <div className="divider-gradient" />

        {/* BENTO GRID */}
        <div className="grid grid-cols-1 md:grid-cols-6 lg:grid-cols-12 gap-6">
          {/* 1. Language (Span 4) */}
          <BentoSettingCard
            title="Language"
            description="Target language for transcription"
            icon={Globe}
            className="md:col-span-6 lg:col-span-4"
          >
            <Select
              value={settings.language}
              onValueChange={(value) => updateSetting("language", value)}
            >
              <SelectTrigger className="mt-auto h-12 rounded-xl">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {options.languages.map((lang) => (
                  <SelectItem key={lang} value={lang}>
                    {lang === "auto" ? "Auto-detect" : lang.toUpperCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </BentoSettingCard>

          {/* 2. Model (Span 4) */}
          <BentoSettingCard
            title="AI Model"
            description="Smaller is faster, larger is smarter"
            icon={Cpu}
            className="md:col-span-6 lg:col-span-4"
          >
            <Select
              value={settings.model}
              onValueChange={handleModelChange}
            >
              <SelectTrigger className="mt-auto h-12 rounded-xl">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {options.models.map((model) => (
                  <SelectItem key={model} value={model}>
                    {model.charAt(0).toUpperCase() + model.slice(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </BentoSettingCard>

          {/* 3. Appearance (Span 4) */}
          <BentoSettingCard
            title="Theme"
            description="Customize the interface look"
            icon={Palette}
            className="md:col-span-6 lg:col-span-4"
          >
            <Select
              value={settings.theme}
              onValueChange={(value) =>
                updateSetting("theme", value as Settings["theme"])
              }
            >
              <SelectTrigger className="mt-auto h-12 rounded-xl">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {options.themeOptions.map((theme) => (
                  <SelectItem key={theme} value={theme}>
                    {theme.charAt(0).toUpperCase() + theme.slice(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </BentoSettingCard>

          {/* 4. Microphone (Span 6) */}
          <BentoSettingCard
            title="Microphone Input"
            description="Select your preferred audio capture device"
            icon={Mic}
            className="md:col-span-6 lg:col-span-6"
          >
            <Select
              value={String(settings.microphone)}
              onValueChange={(value) =>
                updateSetting("microphone", Number(value))
              }
            >
              <SelectTrigger className="mt-auto h-12 rounded-xl">
                <div className="flex items-center gap-2">
                  <Mic className="w-4 h-4 opacity-50" />
                  <SelectValue />
                </div>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="-1">Default System Mic</SelectItem>
                {options.microphones.map((mic) => (
                  <SelectItem key={mic.id} value={String(mic.id)}>
                    {mic.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </BentoSettingCard>

          {/* 5. History Retention (Span 6) */}
          <BentoSettingCard
            title="Data Retention"
            description="How long should we keep your transcriptions?"
            icon={Clock}
            className="md:col-span-6 lg:col-span-6"
          >
            <Select
              value={String(settings.retention)}
              onValueChange={(value) =>
                updateSetting("retention", Number(value))
              }
            >
              <SelectTrigger className="mt-auto h-12 rounded-xl">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {retentionEntries.map(([label, days]) => (
                  <SelectItem key={days} value={String(days)}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </BentoSettingCard>

          {/* 6. Audio History (Span 6) */}
          <BentoSettingCard
            title="History Audio"
            description="Optionally keep your dictation audio with each entry"
            icon={FileAudio}
            className="md:col-span-6 lg:col-span-6"
          >
            <div className="mt-auto flex items-center justify-between p-3 rounded-xl bg-secondary/30 hover:bg-secondary/50 transition-colors">
              <Label
                htmlFor="save-audio-history"
                className="font-medium cursor-pointer"
              >
                Save dictation audio to History
              </Label>
              <Switch
                id="save-audio-history"
                checked={settings.saveAudioToHistory}
                onCheckedChange={(checked) =>
                  updateSetting("saveAudioToHistory", checked)
                }
              />
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              Audio stays on your device. When enabled, History items show an Audio badge with playback.
            </p>
          </BentoSettingCard>

          {/* 7. System (Auto Start) (Span 4) */}
          <BentoSettingCard
            title="System"
            description="Startup behavior"
            icon={Zap}
            className="md:col-span-6 lg:col-span-4"
          >
            <div className="mt-auto flex items-center justify-between p-3 rounded-xl bg-secondary/30 hover:bg-secondary/50 transition-colors">
              <Label
                htmlFor="auto-start"
                className="font-medium cursor-pointer"
              >
                Start with Windows
              </Label>
              <Switch
                id="auto-start"
                checked={settings.autoStart}
                onCheckedChange={(checked) =>
                  updateSetting("autoStart", checked)
                }
              />
            </div>
          </BentoSettingCard>

          {/* 8. Data Folder (Span 4) */}
          <BentoSettingCard
            title="Storage"
            description="Local data location"
            icon={FolderOpen}
            className="md:col-span-6 lg:col-span-4"
          >
            <div className="mt-auto">
              <button
                onClick={() => api.openDataFolder()}
                className="w-full flex items-center justify-center gap-2 h-12 rounded-xl border border-border/50 bg-background/50 hover:bg-primary/5 hover:border-primary/30 hover:text-primary transition-all text-sm font-medium text-muted-foreground"
              >
                <FolderOpen className="w-4 h-4" />
                Open Data Folder
              </button>
            </div>
          </BentoSettingCard>

          {/* 8. Keyboard Shortcuts (Full Width) */}
          <BentoSettingCard
            title="Keyboard Shortcuts"
            description="Customize recording hotkeys"
            icon={Keyboard}
            className="md:col-span-6 lg:col-span-12"
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Hold Mode */}
              <div className="space-y-4 p-4 rounded-xl bg-secondary/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Hand className="w-5 h-5 text-primary" />
                    <div>
                      <h4 className="font-medium">Hold Mode</h4>
                      <p className="text-xs text-muted-foreground">
                        Hold to record, release to stop
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={settings.holdHotkeyEnabled}
                    onCheckedChange={(checked) =>
                      updateSetting("holdHotkeyEnabled", checked)
                    }
                  />
                </div>

                <HotkeyCapture
                  value={settings.holdHotkey}
                  onChange={(hotkey) => updateSetting("holdHotkey", hotkey)}
                  onValidate={(hotkey) => validateHotkey(hotkey, "holdHotkey")}
                  disabled={!settings.holdHotkeyEnabled}
                />
              </div>

              {/* Toggle Mode */}
              <div className="space-y-4 p-4 rounded-xl bg-secondary/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <ToggleRight className="w-5 h-5 text-primary" />
                    <div>
                      <h4 className="font-medium">Toggle Mode</h4>
                      <p className="text-xs text-muted-foreground">
                        Press once to start, press again to stop
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={settings.toggleHotkeyEnabled}
                    onCheckedChange={(checked) =>
                      updateSetting("toggleHotkeyEnabled", checked)
                    }
                  />
                </div>

                <HotkeyCapture
                  value={settings.toggleHotkey}
                  onChange={(hotkey) => updateSetting("toggleHotkey", hotkey)}
                  onValidate={(hotkey) => validateHotkey(hotkey, "toggleHotkey")}
                  disabled={!settings.toggleHotkeyEnabled}
                />
              </div>
            </div>
          </BentoSettingCard>

          {/* Advanced Section Divider */}
          <div className="md:col-span-6 lg:col-span-12 pt-4">
            <h2 className="text-xl font-semibold tracking-tight text-foreground mb-1">
              Advanced
            </h2>
            <p className="text-sm text-muted-foreground">
              Hardware and performance settings
            </p>
          </div>

          {/* 9. GPU / Device (Span 6) */}
          <BentoSettingCard
            title="Compute Device"
            description="Choose CPU or GPU for transcription"
            icon={Cpu}
            className="md:col-span-6 lg:col-span-6"
          >
            <Select
              value={settings.device}
              onValueChange={handleDeviceChange}
            >
              <SelectTrigger className="h-12 rounded-xl">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {options.deviceOptions.map((device) => (
                  <SelectItem
                    key={device}
                    value={device}
                    disabled={device === "cuda" && !gpuInfo?.cudaAvailable}
                  >
                    {device === "auto"
                      ? "Auto (Recommended)"
                      : device === "cuda"
                        ? `CUDA${!gpuInfo?.cudaAvailable ? " (Unavailable)" : ""}`
                        : "CPU"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {deviceError && (
              <p className="text-xs text-destructive mt-2">{deviceError}</p>
            )}
            {gpuInfo && (
              <div className="mt-4 p-3 rounded-xl bg-secondary/30 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Status</span>
                  <span className={
                    gpuInfo.cudaAvailable
                      ? "text-green-500"
                      : gpuInfo.gpuName && !gpuInfo.cudnnAvailable
                        ? "text-amber-500"
                        : "text-muted-foreground"
                  }>
                    {gpuInfo.cudaAvailable
                      ? "CUDA Available"
                      : gpuInfo.gpuName && !gpuInfo.cudnnAvailable
                        ? "cuDNN Missing"
                        : "CPU Only"}
                  </span>
                </div>
                {gpuInfo.gpuName && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">GPU</span>
                    <span className="text-foreground truncate ml-2 max-w-[180px]" title={gpuInfo.gpuName}>
                      {gpuInfo.gpuName}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Active</span>
                  <span className="text-foreground">
                    {gpuInfo.currentDevice.toUpperCase()} ({gpuInfo.currentComputeType})
                  </span>
                </div>
                {gpuInfo.gpuName && !gpuInfo.cudnnAvailable && (
                  <p className="text-xs text-amber-500 pt-1">
                    Install cuDNN 9.x for GPU acceleration
                  </p>
                )}
              </div>
            )}
          </BentoSettingCard>

          {/* 10. Danger Zone (Span 4) */}
          <DangerZoneCard />
        </div>
      </div>

      {/* Model Download Modal */}
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

// BENTO CARD COMPONENT
function BentoSettingCard({
  children,
  title,
  description,
  icon: Icon,
  className,
  iconClass = "text-primary bg-primary/10",
}: {
  children: React.ReactNode;
  title: string;
  description: string;
  icon: React.ElementType;
  className?: string;
  iconClass?: string;
}) {
  return (
    <div
      className={cn(
        "group glass-card flex flex-col justify-between p-6 transition-colors duration-150",
        className
      )}
    >
      <div className="flex items-start gap-4 mb-6">
        <div
          className={cn(
            "p-2.5 rounded-xl border border-primary/20",
            iconClass
          )}
        >
          <Icon className="w-5 h-5" />
        </div>
        <div className="space-y-1 flex-1">
          <h3 className="text-base font-semibold tracking-tight">{title}</h3>
          <p className="text-sm text-muted-foreground line-clamp-2">
            {description}
          </p>
        </div>
      </div>
      <div className="flex-grow flex flex-col justify-end">{children}</div>
    </div>
  );
}

// DANGER ZONE CARD WITH DELETE OPTIONS
function DangerZoneCard() {
  const [deleteAppData, setDeleteAppData] = useState(true);
  const [deleteModels, setDeleteModels] = useState(false);
  const [deleteCudaLibs, setDeleteCudaLibs] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      // Delete app data (history, settings, etc.)
      if (deleteAppData) {
        await api.resetAllData();
      }

      // Delete models (clear HuggingFace cache)
      if (deleteModels) {
        await api.clearModelCache();
      }

      // Delete CUDA libraries (cuDNN + cuBLAS)
      if (deleteCudaLibs) {
        await api.clearCudaLibs();
      }

      const parts = [];
      if (deleteAppData) parts.push("app data");
      if (deleteModels) parts.push("models");
      if (deleteCudaLibs) parts.push("CUDA libraries");
      const message = parts.length > 0 ? `Deleted: ${parts.join(", ")}` : "Nothing deleted";

      toast.success(`${message} - returning to setup`);
      setTimeout(() => {
        window.location.hash = "/onboarding";
        window.location.reload();
      }, 500);
    } catch (error) {
      console.error("Failed to delete data:", error);
      toast.error("Failed to delete data");
    } finally {
      setIsDeleting(false);
    }
  };

  const canDelete = deleteAppData || deleteModels || deleteCudaLibs;

  return (
    <BentoSettingCard
      title="Danger Zone"
      description="Irreversible actions"
      icon={Trash2}
      className="md:col-span-6 lg:col-span-4 !border-destructive/20"
      iconClass="text-destructive bg-destructive/10"
    >
      <div className="mt-auto">
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button className="w-full flex items-center justify-center gap-2 h-12 rounded-xl border border-destructive/30 bg-destructive/5 hover:bg-destructive hover:text-white hover:border-destructive transition-all text-sm font-medium text-destructive">
              <Trash2 className="w-4 h-4" />
              Reset Data
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent className="glass-strong rounded-2xl">
            <AlertDialogHeader>
              <AlertDialogTitle>What would you like to delete?</AlertDialogTitle>
              <AlertDialogDescription>
                Select what data to remove. These actions cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>

            <div className="space-y-4 py-4">
              {/* App Data Option */}
              <label className="flex items-start gap-3 p-3 rounded-xl bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer">
                <Checkbox
                  checked={deleteAppData}
                  onCheckedChange={(checked) => setDeleteAppData(checked === true)}
                  className="mt-0.5"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <FolderOpen className="w-4 h-4 text-muted-foreground" />
                    <span className="font-medium text-sm">App Data</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    History, settings, preferences, audio recordings
                  </p>
                  <code className="text-[10px] text-muted-foreground/70 mt-1 block">
                    %USERPROFILE%\.VoiceFlow\
                  </code>
                </div>
              </label>

              {/* Models Option */}
              <label className="flex items-start gap-3 p-3 rounded-xl bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer">
                <Checkbox
                  checked={deleteModels}
                  onCheckedChange={(checked) => setDeleteModels(checked === true)}
                  className="mt-0.5"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-4 h-4 text-muted-foreground" />
                    <span className="font-medium text-sm">AI Models</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Downloaded Whisper models (requires re-download)
                  </p>
                  <code className="text-[10px] text-muted-foreground/70 mt-1 block">
                    %USERPROFILE%\.cache\huggingface\hub\
                  </code>
                </div>
              </label>

              {/* CUDA Libraries Option */}
              <label className="flex items-start gap-3 p-3 rounded-xl bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer">
                <Checkbox
                  checked={deleteCudaLibs}
                  onCheckedChange={(checked) => setDeleteCudaLibs(checked === true)}
                  className="mt-0.5"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-muted-foreground" />
                    <span className="font-medium text-sm">CUDA Libraries</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    cuDNN + cuBLAS for GPU acceleration (requires re-download)
                  </p>
                  <code className="text-[10px] text-muted-foreground/70 mt-1 block">
                    %USERPROFILE%\.VoiceFlow\cuda\
                  </code>
                </div>
              </label>
            </div>

            <AlertDialogFooter>
              <AlertDialogCancel className="rounded-xl">
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-white hover:bg-destructive/90 rounded-xl disabled:opacity-50"
                onClick={handleDelete}
                disabled={!canDelete || isDeleting}
              >
                {isDeleting ? "Deleting..." : "Delete Selected"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </BentoSettingCard>
  );
}
