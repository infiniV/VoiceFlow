/**
 * Theme palettes aligned with VoiceKey (SimpleVoiceKeyboard iOS).
 * CSS variables for each palette live in index.css under [data-palette="…"].
 */

export type ThemePalette =
  | "midnight"
  | "aurora"
  | "ember"
  | "ocean"
  | "snowfall"
  | "neonCity";

export interface ThemePaletteMeta {
  id: ThemePalette;
  name: string;
  icon: string;
  isDark: boolean;
  accent: string;
  accentEnd: string;
  background: string;
}

export const THEME_PALETTES: ThemePaletteMeta[] = [
  {
    id: "midnight",
    name: "Midnight",
    icon: "moon",
    isDark: true,
    background: "#0D0D14",
    accent: "#7C6AFF",
    accentEnd: "#4ECDC4",
  },
  {
    id: "aurora",
    name: "Aurora",
    icon: "sparkles",
    isDark: true,
    background: "#0A0E1A",
    accent: "#38BDF8",
    accentEnd: "#818CF8",
  },
  {
    id: "ember",
    name: "Ember",
    icon: "flame",
    isDark: true,
    background: "#120C0A",
    accent: "#FF6B35",
    accentEnd: "#FF2E63",
  },
  {
    id: "ocean",
    name: "Ocean",
    icon: "waves",
    isDark: true,
    background: "#0A1628",
    accent: "#00D4AA",
    accentEnd: "#0099FF",
  },
  {
    id: "snowfall",
    name: "Snowfall",
    icon: "snowflake",
    isDark: false,
    background: "#F8FAFC",
    accent: "#6366F1",
    accentEnd: "#8B5CF6",
  },
  {
    id: "neonCity",
    name: "Neon City",
    icon: "building",
    isDark: true,
    background: "#0D001A",
    accent: "#FF00FF",
    accentEnd: "#00FFFF",
  },
];

const LEGACY_THEME_MAP: Record<string, ThemePalette> = {
  dark: "midnight",
  light: "snowfall",
  system: "midnight",
};

export function normalizePalette(theme: string): ThemePalette {
  const mapped = LEGACY_THEME_MAP[theme] ?? theme;
  if (THEME_PALETTES.some((p) => p.id === mapped)) {
    return mapped as ThemePalette;
  }
  return "midnight";
}

export function getPaletteMeta(id: string): ThemePaletteMeta {
  return (
    THEME_PALETTES.find((p) => p.id === normalizePalette(id)) ?? THEME_PALETTES[0]
  );
}

/** Apply palette to document — sets data-palette and dark/light class. */
export function applyThemePalette(theme: string) {
  const palette = normalizePalette(theme);
  const root = document.documentElement;
  root.setAttribute("data-palette", palette);
  root.classList.toggle("dark", getPaletteMeta(palette).isDark);
}
