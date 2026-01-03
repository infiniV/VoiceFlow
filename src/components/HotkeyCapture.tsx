import { useState, useEffect, useRef, useCallback } from "react";
import { Kbd, KbdGroup } from "@/components/ui/kbd";
import { cn } from "@/lib/utils";

interface HotkeyCaptureProps {
  value: string;
  onChange: (hotkey: string) => void;
  onValidate?: (hotkey: string) => Promise<{ valid: boolean; error: string | null }>;
  disabled?: boolean;
  placeholder?: string;
}

// Map keyboard event keys to keyboard library format
const KEY_MAP: Record<string, string> = {
  Control: "ctrl",
  Shift: "shift",
  Alt: "alt",
  Meta: "win",
  " ": "space",
};

const MODIFIER_KEYS = new Set(["ctrl", "shift", "alt", "win"]);

// Canonical modifier order - must match backend MODIFIER_ORDER in hotkey.py
const MODIFIER_ORDER = ["ctrl", "alt", "shift", "win"];

function normalizeKey(key: string): string {
  return KEY_MAP[key] || key.toLowerCase();
}

function formatKeyForDisplay(key: string): string {
  // Capitalize first letter
  return key.charAt(0).toUpperCase() + key.slice(1);
}

export function HotkeyCapture({
  value,
  onChange,
  onValidate,
  disabled = false,
  placeholder = "Click to set hotkey",
}: HotkeyCaptureProps) {
  const [isCapturing, setIsCapturing] = useState(false);
  const [pressedKeys, setPressedKeys] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const captureRef = useRef<HTMLButtonElement>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!isCapturing) return;

      // Handle Escape to cancel
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        setIsCapturing(false);
        setPressedKeys(new Set());
        setError(null);
        return;
      }

      e.preventDefault();
      e.stopPropagation();

      const key = normalizeKey(e.key);
      setPressedKeys((prev) => new Set(prev).add(key));
    },
    [isCapturing]
  );

  const handleKeyUp = useCallback(
    async (e: KeyboardEvent) => {
      if (!isCapturing) return;

      e.preventDefault();
      e.stopPropagation();

      // When any key is released, capture the current combination
      if (pressedKeys.size >= 2) {
        const pressed = Array.from(pressedKeys);
        const mods = pressed.filter((k) => MODIFIER_KEYS.has(k));
        const mainKeys = pressed.filter((k) => !MODIFIER_KEYS.has(k));

        // Valid combinations:
        // 1. At least one modifier + at least one non-modifier key (e.g., "ctrl+r")
        // 2. At least two modifiers (e.g., "ctrl+win") - these are also valid hotkeys
        const hasValidModifierCombo = mods.length > 0 && mainKeys.length > 0;
        const hasMultipleModifiers = mods.length >= 2;

        if (hasValidModifierCombo || hasMultipleModifiers) {
          // Sort modifiers in canonical order to match backend
          const sortedMods = mods.sort(
            (a, b) => MODIFIER_ORDER.indexOf(a) - MODIFIER_ORDER.indexOf(b)
          );
          // Sort main keys alphabetically for consistency
          const sortedMainKeys = mainKeys.sort();
          const hotkey = [...sortedMods, ...sortedMainKeys].join("+");

          // Validate
          if (onValidate) {
            try {
              const result = await onValidate(hotkey);
              if (!result.valid) {
                setError(result.error);
                setPressedKeys(new Set());
                return;
              }
            } catch {
              setError("Validation failed");
              setPressedKeys(new Set());
              return;
            }
          }

          setError(null);
          onChange(hotkey);
          setIsCapturing(false);
          setPressedKeys(new Set());
          return;
        }
      }

      // Remove the released key
      const key = normalizeKey(e.key);
      setPressedKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    },
    [isCapturing, pressedKeys, onChange, onValidate]
  );

  useEffect(() => {
    if (isCapturing) {
      window.addEventListener("keydown", handleKeyDown, true);
      window.addEventListener("keyup", handleKeyUp, true);

      return () => {
        window.removeEventListener("keydown", handleKeyDown, true);
        window.removeEventListener("keyup", handleKeyUp, true);
      };
    }
  }, [isCapturing, handleKeyDown, handleKeyUp]);

  // Click outside to cancel
  useEffect(() => {
    if (isCapturing) {
      const handleClickOutside = (e: MouseEvent) => {
        if (
          captureRef.current &&
          !captureRef.current.contains(e.target as Node)
        ) {
          setIsCapturing(false);
          setPressedKeys(new Set());
          setError(null);
        }
      };

      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isCapturing]);

  const displayKeys = isCapturing
    ? Array.from(pressedKeys)
    : value
      ? value.split("+")
      : [];

  return (
    <div className="space-y-2">
      <button
        ref={captureRef}
        type="button"
        onClick={() => {
          if (!disabled) {
            setIsCapturing(true);
            setError(null);
            setPressedKeys(new Set());
          }
        }}
        disabled={disabled}
        className={cn(
          "w-full h-12 flex items-center justify-center rounded-xl border border-border/50 bg-background/50 transition-all text-sm font-medium",
          "hover:bg-primary/5 hover:border-primary/30",
          isCapturing &&
            "ring-2 ring-primary ring-offset-2 ring-offset-background bg-primary/5 border-primary/50",
          disabled && "opacity-50 cursor-not-allowed hover:bg-background/50 hover:border-border/50"
        )}
      >
        {isCapturing ? (
          displayKeys.length > 0 ? (
            <KbdGroup>
              {displayKeys.map((key, i) => (
                <Kbd key={i} className="px-2 py-1 text-sm">
                  {formatKeyForDisplay(key)}
                </Kbd>
              ))}
            </KbdGroup>
          ) : (
            <span className="text-muted-foreground animate-pulse">
              Press keys...
            </span>
          )
        ) : displayKeys.length > 0 ? (
          <KbdGroup>
            {displayKeys.map((key, i) => (
              <Kbd key={i} className="px-2 py-1 text-sm">
                {formatKeyForDisplay(key)}
              </Kbd>
            ))}
          </KbdGroup>
        ) : (
          <span className="text-muted-foreground">{placeholder}</span>
        )}
      </button>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
