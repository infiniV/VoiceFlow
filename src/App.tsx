import { useEffect, useState, useCallback } from "react";
import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Onboarding } from "@/pages/Onboarding";
import { Dashboard } from "@/pages/Dashboard";
import { Popup } from "@/pages/Popup";
import { Toaster } from "@/components/ui/sonner";
import { ModelRecoveryModal } from "@/components/ModelRecoveryModal";
import type { Settings } from "@/lib/types";

// Detect Linux platform and add reduced-effects class
// Qt WebEngine on Linux often falls back to software rendering,
// making backdrop-filter/blur extremely expensive
// Skip for popup route - it needs transparent background
if (navigator.platform.startsWith("Linux") && window.location.hash !== "#/popup") {
  document.documentElement.classList.add("reduced-effects");
}

// Apply theme to document
function applyTheme(theme: Settings["theme"]) {
  const root = document.documentElement;
  let isDark = false;

  if (theme === "system") {
    isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  } else {
    isDark = theme === "dark";
  }

  if (isDark) {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

function AppRouter() {
  const [loading, setLoading] = useState(true);
  const [onboardingComplete, setOnboardingComplete] = useState(false);
  const [modelMissing, setModelMissing] = useState(false);
  const [currentModel, setCurrentModel] = useState<string>("");

  // Check if this is the popup route - render immediately without loading state
  const isPopupRoute = window.location.hash === "#/popup";

  useEffect(() => {
    // Skip settings check for popup - it doesn't need it
    if (isPopupRoute) {
      setLoading(false);
      return;
    }

    const checkStartup = async () => {
      try {
        const settings = await api.getSettings();
        setOnboardingComplete(settings.onboardingComplete);
        setCurrentModel(settings.model);
        // Apply theme on app load
        applyTheme(settings.theme);

        // If onboarding is complete, check if model is cached
        if (settings.onboardingComplete) {
          try {
            const modelInfo = await api.getModelInfo(settings.model);
            if (!modelInfo.cached) {
              // Model is missing - show recovery modal
              setModelMissing(true);
            }
          } catch (err) {
            console.error("Failed to check model cache:", err);
            // If we can't check, assume it's fine and let the backend handle it
          }
        }
      } catch (error) {
        console.error("Failed to check onboarding:", error);
        // Default to showing onboarding if we can't check
        setOnboardingComplete(false);
      } finally {
        setLoading(false);
      }
    };
    checkStartup();
  }, [isPopupRoute]);

  // Handle model recovery complete
  const handleRecoveryComplete = useCallback(() => {
    setModelMissing(false);
  }, []);

  // For popup, render immediately with no loading state
  if (isPopupRoute) {
    return (
      <Routes>
        <Route path="/popup" element={<Popup />} />
      </Routes>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <>
      <Routes>
        <Route path="/popup" element={<Popup />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/dashboard/*" element={<Dashboard />} />
        <Route
          path="/"
          element={
            <Navigate to={onboardingComplete ? "/dashboard" : "/onboarding"} replace />
          }
        />
      </Routes>

      {/* Model Recovery Modal - shows when model is missing after onboarding */}
      <ModelRecoveryModal
        open={modelMissing}
        modelName={currentModel}
        onComplete={handleRecoveryComplete}
      />
    </>
  );
}

export default function App() {
  return (
    <HashRouter>
      <AppRouter />
      <Toaster position="bottom-right" />
    </HashRouter>
  );
}
