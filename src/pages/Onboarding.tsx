import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ArrowLeft,
  Check,
  Mic,
  AlertCircle,
  Zap,
  Shield,
  Globe,
  Cpu,
  Sparkles,
  Keyboard,
  Download,
  Target,
  HardDrive,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { AudioVisualizer } from "@/components/AudioVisualizer";
import { ModelDownloadProgress } from "@/components/ModelDownloadProgress";
import { api } from "@/lib/api";
import type { Settings, Options } from "@/lib/types";
import {
  MODEL_OPTIONS,
  MODEL_CATEGORIES,
  THEME_OPTIONS,
  ONBOARDING_FEATURES,
  isEnglishOnlyModel,
} from "@/lib/constants";

// --- Step Components ---

const StepWelcome = () => (
  <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500">
    <p className="text-xl font-light leading-relaxed text-muted-foreground max-w-lg">
      Dictation designed for{" "}
      <span className="headline-serif text-foreground">privacy</span> and{" "}
      <span className="headline-serif text-foreground">flow</span>.
    </p>

    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {ONBOARDING_FEATURES.map((feature, idx) => (
        <div
          key={feature.label}
          className="group glass-card flex flex-col items-center text-center gap-3 p-6 transition-all hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-1 animate-in slide-in-from-bottom-4 duration-500"
          style={{ animationDelay: `${idx * 100}ms` }}
        >
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary transition-transform group-hover:scale-110 border border-primary/20">
            <feature.icon className="w-6 h-6" />
          </div>
          <div>
            <p className="font-semibold text-foreground">{feature.label}</p>
            <p className="text-sm text-muted-foreground">{feature.desc}</p>
          </div>
        </div>
      ))}
    </div>
  </div>
);

const StepAudio = ({
  microphone,
  setMicrophone,
  options,
}: {
  microphone: number;
  setMicrophone: (id: number) => void;
  options: Options;
}) => {
  const [amplitude, setAmplitude] = useState(0);
  const [isListening, setIsListening] = useState(false);

  // Listen for amplitude events from backend
  useEffect(() => {
    const handleAmplitude = (e: CustomEvent<number>) => {
      setAmplitude(e.detail);
    };

    document.addEventListener("amplitude" as any, handleAmplitude);

    return () => {
      document.removeEventListener("amplitude" as any, handleAmplitude);
    };
  }, []);

  // Start test recording on mount, stop on unmount
  useEffect(() => {
    let mounted = true;

    const startRecording = async () => {
      try {
        // Start test recording with the initial microphone
        await api.updateSettings({ microphone });
        await api.startTestRecording();
        if (mounted) {
          setIsListening(true);
        }
      } catch (error) {
        console.error("[Audio] Failed to start test recording:", error);
      }
    };

    const timer = setTimeout(startRecording, 100);

    return () => {
      mounted = false;
      clearTimeout(timer);
      // Stop test recording when leaving this step
      api.stopTestRecording().catch(() => {});
      setIsListening(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run on mount/unmount, device changes handled by handleDeviceChange

  // Handle device change - restart recording with new device
  const handleDeviceChange = async (backendDeviceId: string) => {
    const backendId = Number(backendDeviceId);
    setMicrophone(backendId);

    // Stop current recording
    try {
      await api.stopTestRecording();
    } catch {
      // Ignore errors
    }

    // Update setting and restart
    try {
      await api.updateSettings({ microphone: backendId });
      await api.startTestRecording();
      setIsListening(true);
    } catch (error) {
      console.error("[Audio] Failed to restart recording:", error);
    }
  };

  return (
    <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500 max-w-xl">
      <div className="glass-card p-1">
        <Select
          value={String(microphone)}
          onValueChange={handleDeviceChange}
        >
          <SelectTrigger className="h-14 text-base bg-transparent border-0 rounded-xl px-4 focus:ring-0 focus:ring-offset-0">
            <SelectValue placeholder="Select a microphone" />
          </SelectTrigger>
          <SelectContent className="border-border/50 bg-popover/95 backdrop-blur-xl shadow-2xl rounded-xl">
            {options.microphones.map((mic) => (
              <SelectItem
                key={mic.id}
                value={String(mic.id)}
                className="py-3 rounded-lg cursor-pointer"
              >
                <span className="flex items-center gap-3">
                  <Mic className="w-4 h-4 text-muted-foreground" />
                  <span>{mic.name}</span>
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="h-24 w-full glass-card flex items-center justify-center p-4 relative">
        {isListening ? (
          <AudioVisualizer
            amplitude={amplitude}
            bars={40}
            className="gap-1 h-14 text-primary"
          />
        ) : (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <span className="w-2 h-2 rounded-full bg-muted animate-pulse" />
            Waiting for microphone...
          </div>
        )}

        <div
          className={`absolute right-4 top-4 w-2 h-2 rounded-full transition-all ${isListening ? "bg-primary" : "bg-muted-foreground/30"}`}
        />
      </div>

      <p className="text-sm text-muted-foreground leading-relaxed">
        Speak now to test your input levels. The visualizer should respond to your voice.
      </p>
    </div>
  );
};

// Rating bar component for speed/accuracy
const RatingBar = ({ value, max = 5, label }: { value: number; max?: number; label: string }) => (
  <div className="flex items-center gap-2">
    <span className="text-xs text-muted-foreground w-16">{label}</span>
    <div className="flex gap-0.5 flex-1">
      {Array.from({ length: max }).map((_, i) => (
        <div
          key={i}
          className={`h-1.5 flex-1 rounded-full transition-colors ${
            i < value ? "bg-primary" : "bg-muted-foreground/20"
          }`}
        />
      ))}
    </div>
  </div>
);

const StepModel = ({
  language,
  setLanguage,
  model,
  setModel,
  options,
}: {
  language: string;
  setLanguage: (l: string) => void;
  model: string;
  setModel: (m: string) => void;
  options: Options;
}) => {
  const selectedModel = MODEL_OPTIONS.find((m) => m.id === model);
  const categoryInfo = selectedModel ? MODEL_CATEGORIES[selectedModel.category] : null;

  // Auto-switch language when selecting English-only model
  const handleModelSelect = (modelId: string) => {
    setModel(modelId);
    if (isEnglishOnlyModel(modelId) && language !== "en") {
      setLanguage("en");
    }
  };

  return (
    <div className="flex gap-6 animate-in slide-in-from-bottom-4 duration-500 w-full max-w-6xl">
      {/* Left side - Model grid */}
      <div className="flex-1 space-y-4">
        <div className="glass-card p-1 max-w-sm">
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="h-11 text-sm bg-transparent border-0 rounded-lg px-4 focus:ring-0 focus:ring-offset-0">
              <span className="flex items-center gap-3 w-full">
                <Globe className="w-4 h-4 text-muted-foreground" />
                <span className="text-muted-foreground">Language:</span>
                <SelectValue />
              </span>
            </SelectTrigger>
            <SelectContent className="border-border/50 bg-popover/95 backdrop-blur-xl shadow-2xl rounded-xl max-h-[280px]">
              {options.languages.map((lang) => (
                <SelectItem
                  key={lang}
                  value={lang}
                  className="py-2.5 rounded-lg cursor-pointer"
                >
                  {lang === "auto" ? "Auto-detect" : lang.toUpperCase()}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Cpu className="w-4 h-4" />
              Processing Model
            </span>
            <span className="badge-glow !py-1 !px-2.5 !text-[10px]">
              <Shield className="w-3 h-3" />
              Local Only
            </span>
          </div>

          <div
            className="grid grid-cols-4 gap-1.5"
            role="radiogroup"
            aria-label="Select processing model"
          >
            {MODEL_OPTIONS.map((m, idx) => {
              const isActive = model === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  className={`
                    relative p-2.5 rounded-md text-left transition-all duration-200 group
                    flex flex-col gap-0 animate-in slide-in-from-bottom-4
                    ${
                      isActive
                        ? "glass-strong border-primary/50 shadow-md shadow-primary/10"
                        : "glass-card hover:bg-muted/50"
                    }
                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1
                  `}
                  style={{ animationDelay: `${idx * 20}ms` }}
                  onClick={() => handleModelSelect(m.id)}
                >
                  <div className="flex items-center justify-between w-full">
                    <span
                      className={`font-medium text-xs ${isActive ? "text-primary" : "text-foreground"}`}
                    >
                      {m.label}
                    </span>
                    {isActive && (
                      <div
                        className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_6px_currentColor]"
                        aria-hidden="true"
                      />
                    )}
                  </div>
                  <span className="text-[10px] text-muted-foreground/70">
                    {m.detail}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Right side - Model details card */}
      {selectedModel && (
        <div className="w-72 flex-shrink-0 animate-in slide-in-from-right-4 duration-300">
          <div className="glass-card p-4 space-y-4 h-[360px] overflow-y-auto">
            {/* Header */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-lg text-foreground">{selectedModel.label}</h3>
                {categoryInfo && (
                  <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted/50 ${categoryInfo.color}`}>
                    {categoryInfo.label}
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{selectedModel.desc}</p>
            </div>

            {/* Ratings */}
            <div className="space-y-2 py-2 border-y border-border/30">
              <RatingBar value={selectedModel.speed} label="Speed" />
              <RatingBar value={selectedModel.accuracy} label="Accuracy" />
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3">
              <div className="flex items-center gap-2">
                <Cpu className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">{selectedModel.detail}</span>
              </div>
              <div className="flex items-center gap-2">
                <HardDrive className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">{selectedModel.size}</span>
              </div>
            </div>

            {/* Best for */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Target className="w-3.5 h-3.5" />
                Best for
              </div>
              <p className="text-xs text-foreground/80 leading-relaxed">
                {selectedModel.bestFor}
              </p>
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Info className="w-3.5 h-3.5" />
                About
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {selectedModel.description}
              </p>
            </div>

          </div>
        </div>
      )}
    </div>
  );
};

const StepTheme = ({
  theme,
  setTheme,
  autoStart,
  setAutoStart,
}: {
  theme: Settings["theme"];
  setTheme: (t: Settings["theme"]) => void;
  autoStart: boolean;
  setAutoStart: (b: boolean) => void;
}) => (
  <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
    <fieldset>
      <legend className="text-sm font-medium text-muted-foreground mb-4">
        Interface Theme
      </legend>
      <div
        className="grid grid-cols-3 gap-4 max-w-md"
        role="radiogroup"
        aria-label="Theme selection"
      >
        {THEME_OPTIONS.map((opt, idx) => {
          const isActive = theme === opt.val;
          return (
            <button
              key={opt.val}
              type="button"
              role="radio"
              aria-checked={isActive}
              className={`
                relative p-5 rounded-2xl flex flex-col items-center gap-4 transition-all duration-300 animate-in slide-in-from-bottom-4
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2
                ${
                  isActive
                    ? "glass-strong border-primary/50 shadow-lg shadow-primary/10 scale-105"
                    : "glass-card hover:shadow-md hover:-translate-y-0.5"
                }
              `}
              style={{ animationDelay: `${idx * 50}ms` }}
              onClick={() => setTheme(opt.val as Settings["theme"])}
            >
              <div
                className={`w-14 h-14 rounded-full border-2 shadow-sm transition-all duration-500 ${isActive ? "rotate-12 scale-110" : ""} ${
                  opt.val === "light"
                    ? "bg-[#faf8f5] border-gray-200"
                    : opt.val === "dark"
                      ? "bg-[#050a0f] border-gray-700"
                      : "bg-gradient-to-br from-[#faf8f5] to-[#050a0f] border-gray-400"
                }`}
              />
              <span
                className={`text-sm font-medium ${isActive ? "text-primary" : "text-muted-foreground"}`}
              >
                {opt.label}
              </span>
            </button>
          );
        })}
      </div>
    </fieldset>

    <div className="glass-card p-5 max-w-md transition-colors hover:shadow-md">
      <label className="flex items-center justify-between cursor-pointer">
        <div className="space-y-1">
          <span className="block font-medium text-foreground flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" />
            Auto-start VoiceFlow
          </span>
          <span className="block text-sm text-muted-foreground">
            Launch instantly when Windows starts
          </span>
        </div>
        <Switch
          checked={autoStart}
          onCheckedChange={setAutoStart}
          className="data-[state=checked]:bg-primary"
        />
      </label>
    </div>
  </div>
);

const StepFinal = () => (
  <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500 max-w-lg">
    <div className="glass-card p-8 text-center relative overflow-hidden">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="orb orb-primary w-[200px] h-[200px] absolute -top-20 left-1/2 -translate-x-1/2 opacity-30" />
      </div>

      <div className="relative z-10">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
          <Keyboard className="w-8 h-8 text-primary" />
        </div>

        <p className="badge-glow mx-auto mb-6 w-fit">Global Shortcut</p>

        <div className="flex items-center justify-center gap-4 mb-6">
          <kbd className="min-w-[80px] py-3 rounded-xl bg-background border border-border/50 text-2xl font-bold text-foreground shadow-[0_4px_0_0_rgba(0,0,0,0.1)] dark:shadow-[0_4px_0_0_rgba(255,255,255,0.05)] transition-transform hover:translate-y-0.5 hover:shadow-[0_2px_0_0_rgba(0,0,0,0.1)]">
            Ctrl
          </kbd>
          <span className="text-xl text-muted-foreground/50">+</span>
          <kbd className="min-w-[80px] py-3 rounded-xl bg-background border border-border/50 text-2xl font-bold text-foreground shadow-[0_4px_0_0_rgba(0,0,0,0.1)] dark:shadow-[0_4px_0_0_rgba(255,255,255,0.05)] transition-transform hover:translate-y-0.5 hover:shadow-[0_2px_0_0_rgba(0,0,0,0.1)]">
            Win
          </kbd>
        </div>
        <p className="text-sm text-muted-foreground">
          Hold to record, release to transcribe.
        </p>
      </div>
    </div>

    <div className="glass-card p-5 flex items-center gap-4">
      <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center flex-shrink-0">
        <Sparkles className="w-5 h-5 text-primary" />
      </div>
      <p className="text-sm text-muted-foreground leading-relaxed">
        VoiceFlow runs quietly in the system tray. Press the shortcut anytime, anywhere to start dictating.
      </p>
    </div>
  </div>
);

// Step configuration
const STEPS_CONFIG = [
  {
    id: "welcome",
    title: "Welcome to VoiceFlow",
    subtitle: "Transform your voice into text with local AI processing.",
    icon: Sparkles,
  },
  {
    id: "audio",
    title: "Configure Audio",
    subtitle: "Select your microphone and test the input levels.",
    icon: Mic,
  },
  {
    id: "model",
    title: "Choose Model",
    subtitle: "Select the AI model and language for transcription.",
    icon: Cpu,
  },
  {
    id: "download",
    title: "Download Model",
    subtitle: "Downloading your selected AI model for offline use.",
    icon: Download,
  },
  {
    id: "theme",
    title: "Personalize",
    subtitle: "Choose your theme and startup preferences.",
    icon: Zap,
  },
  {
    id: "final",
    title: "You're All Set",
    subtitle: "Start dictating with a simple keyboard shortcut.",
    icon: Check,
  },
];

export function Onboarding() {
  const navigate = useNavigate();
  const [options, setOptions] = useState<Options | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);

  // Form state
  const [language, setLanguage] = useState("auto");
  const [model, setModel] = useState("tiny");
  const [autoStart, setAutoStart] = useState(true);
  const [retention] = useState(-1);
  const [theme, setTheme] = useState<Settings["theme"]>("system");
  const [microphone, setMicrophone] = useState<number>(0);

  useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        const optionsData = await api.getOptions();
        setOptions(optionsData);
        if (optionsData.microphones.length > 0) {
          setMicrophone(optionsData.microphones[0].id);
        }
      } catch (err) {
        console.error("Failed to load options:", err);
        setError(
          "Failed to load configuration. Please restart the application."
        );
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Apply theme in real-time
  useEffect(() => {
    const root = document.documentElement;
    let isDark =
      theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
        : theme === "dark";

    if (isDark) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  const handleFinish = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.updateSettings({
        language,
        model,
        autoStart,
        retention,
        theme,
        microphone,
        onboardingComplete: true,
      });
      navigate("/dashboard");
    } catch (err) {
      console.error("Failed to save settings:", err);
      setError("Failed to save settings. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const nextStep = () => setStep((s) => s + 1);
  const prevStep = () => setStep((s) => s - 1);

  // Track if download is actively in progress
  const [isDownloading, setIsDownloading] = useState(false);

  // Handle download state changes
  const handleDownloadStart = () => setIsDownloading(true);
  const handleDownloadComplete = (_success: boolean) => setIsDownloading(false);

  // Handle download cancellation - go back to model selection
  const handleDownloadCancel = () => {
    setIsDownloading(false);
    prevStep();
  };

  // --- Render States ---

  if (loading) {
    return (
      <main
        className="min-h-screen flex items-center justify-center bg-background relative overflow-hidden"
        aria-busy="true"
      >
        <div className="fixed inset-0 bg-grid opacity-20 pointer-events-none" />
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="orb orb-primary w-[400px] h-[400px] absolute top-1/4 -left-40 opacity-30" />
          <div className="orb orb-secondary w-[300px] h-[300px] absolute bottom-1/4 -right-40 opacity-20" />
        </div>

        <div className="relative flex flex-col items-center gap-6 z-10">
          <div className="w-16 h-16 rounded-2xl glass-strong flex items-center justify-center shadow-xl">
            <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          </div>
          <div className="text-center space-y-2">
            <p className="text-lg font-medium text-foreground">
              Initializing Voice<span className="headline-serif text-primary">Flow</span>
            </p>
            <p className="text-sm text-muted-foreground">
              Preparing your experience...
            </p>
          </div>
        </div>
      </main>
    );
  }

  if (error && !options) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-background relative overflow-hidden">
        <div className="fixed inset-0 bg-grid opacity-20 pointer-events-none" />
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="orb orb-accent w-[300px] h-[300px] absolute top-1/3 left-1/4 opacity-20" />
        </div>

        <div
          className="relative glass-card p-8 max-w-md text-center shadow-2xl z-10"
          role="alert"
        >
          <div className="w-14 h-14 rounded-2xl bg-destructive/10 flex items-center justify-center mx-auto mb-6">
            <AlertCircle
              className="w-7 h-7 text-destructive"
              aria-hidden="true"
            />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-2">
            Something went wrong
          </h2>
          <p className="text-muted-foreground mb-6">{error}</p>
          <Button
            onClick={() => window.location.reload()}
            className="rounded-xl w-full"
          >
            Try Again
          </Button>
        </div>
      </main>
    );
  }

  if (!options) return null;

  const currentStepConfig = STEPS_CONFIG[step];
  const isLastStep = step === STEPS_CONFIG.length - 1;
  const isFirstStep = step === 0;
  const StepIcon = currentStepConfig.icon;

  const renderStepContent = () => {
    switch (step) {
      case 0:
        return <StepWelcome />;
      case 1:
        return (
          <StepAudio
            microphone={microphone}
            setMicrophone={setMicrophone}
            options={options}
          />
        );
      case 2:
        return (
          <StepModel
            language={language}
            setLanguage={setLanguage}
            model={model}
            setModel={setModel}
            options={options}
          />
        );
      case 3:
        return (
          <ModelDownloadProgress
            modelName={model}
            onStart={handleDownloadStart}
            onComplete={handleDownloadComplete}
            onCancel={handleDownloadCancel}
            autoStart={true}
          />
        );
      case 4:
        return (
          <StepTheme
            theme={theme}
            setTheme={setTheme}
            autoStart={autoStart}
            setAutoStart={setAutoStart}
          />
        );
      case 5:
        return <StepFinal />;
      default:
        return null;
    }
  };


  return (
    <main className="min-h-screen flex flex-col bg-background relative overflow-hidden selection:bg-primary/20">
      {/* Ambient background */}
      <div className="fixed inset-0 bg-grid opacity-15 pointer-events-none" />
      <div
        className="fixed inset-0 overflow-hidden pointer-events-none"
        aria-hidden="true"
      >
        <div className="orb orb-primary w-[500px] h-[500px] absolute -top-40 -left-40 opacity-25" />
        <div className="orb orb-secondary w-[400px] h-[400px] absolute top-1/2 -right-40 opacity-20" />
        <div className="orb orb-accent w-[300px] h-[300px] absolute -bottom-20 left-1/3 opacity-15" />
      </div>

      {/* Error toast */}
      {error && options && (
        <div
          role="alert"
          className="fixed top-6 left-1/2 -translate-x-1/2 z-50 glass-strong text-destructive px-6 py-3 rounded-full flex items-center gap-3 shadow-lg animate-in slide-in-from-top-4"
        >
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm font-medium">{error}</span>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col relative z-10 p-8 md:p-12 lg:p-16">
        {/* Progress indicator */}
        <div className="flex justify-center gap-2 mb-12">
          {STEPS_CONFIG.map((_, idx) => (
            <button
              key={idx}
              onClick={() => idx < step && setStep(idx)}
              disabled={idx > step}
              className={`h-1.5 rounded-full transition-all duration-500 ease-out ${
                idx === step
                  ? "w-10 bg-primary"
                  : idx < step
                    ? "w-6 bg-primary/50 hover:bg-primary/70 cursor-pointer"
                    : "w-2 bg-muted-foreground/20"
              }`}
            />
          ))}
        </div>

        {/* Header */}
        <header className="text-center mb-10 space-y-4">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-4 animate-in zoom-in duration-300">
            <StepIcon className="w-7 h-7 text-primary" />
          </div>

          <div className="space-y-2">
            <span className="badge-glow">Step {step + 1} of {STEPS_CONFIG.length}</span>
            <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold tracking-tight text-foreground">
              {currentStepConfig.title.split(" ")[0]}{" "}
              <span className="headline-serif text-primary">
                {currentStepConfig.title.split(" ").slice(1).join(" ")}
              </span>
            </h1>
            <p className="text-muted-foreground font-light text-lg">
              {currentStepConfig.subtitle}
            </p>
          </div>
        </header>

        {/* Step Content - Fixed height to prevent layout shift */}
        <div className="flex-1 flex items-start justify-center min-h-0 overflow-y-auto">
          {renderStepContent()}
        </div>

        {/* Navigation - Fixed at bottom */}
        <div className="flex items-center justify-center gap-4 pt-6 flex-shrink-0">
          {!isFirstStep && (
            <Button
              variant="ghost"
              size="lg"
              onClick={prevStep}
              disabled={isDownloading}
              className="rounded-xl text-muted-foreground hover:text-foreground px-6"
            >
              <ArrowLeft className="mr-2 w-4 h-4" />
              Back
            </Button>
          )}

          <Button
            variant="glow"
            size="lg"
            onClick={isLastStep ? handleFinish : nextStep}
            disabled={saving || isDownloading}
            className="rounded-xl min-w-[160px]"
          >
            {saving ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Saving...
              </>
            ) : isLastStep ? (
              <>
                Get Started
                <Check className="w-4 h-4" />
              </>
            ) : (
              <>
                Continue
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Footer */}
      <p className="text-center text-xs text-muted-foreground/50 pb-6 relative z-10">
        All processing happens locally on your device. Your voice never leaves your computer.
      </p>
    </main>
  );
}
