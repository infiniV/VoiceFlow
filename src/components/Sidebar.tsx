import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { History, Radio, Settings, Github, Heart, MessageSquare, Mic, Brain, PenLine, Link2 } from "lucide-react";
import { cn, formatHotkeyForDisplay } from "@/lib/utils";
import { api } from "@/lib/api";
import { APP_VERSION } from "@/lib/constants";

const GITHUB_REPO_URL = "https://github.com/infiniV/Dictore";
const FALLBACK_HOTKEY = "ctrl+win";

const navItems: Array<{
  to: string;
  icon: React.ElementType;
  label: string;
  disabled?: boolean;
}> = [
  { to: "/dashboard", icon: Mic, label: "Record" },
  { to: "/dashboard/meetings", icon: Radio, label: "Meetings" },
  { to: "/dashboard/history", icon: History, label: "History" },
  { to: "/dashboard/insights", icon: Brain, label: "Insights", disabled: true },
  { to: "/dashboard/create", icon: PenLine, label: "Create", disabled: true },
  { to: "/dashboard/links", icon: Link2, label: "Links", disabled: true },
  { to: "/dashboard/settings", icon: Settings, label: "Settings" },
];

interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const [hotkeyDisplay, setHotkeyDisplay] = useState<string>(formatHotkeyForDisplay(FALLBACK_HOTKEY));

  useEffect(() => {
    let cancelled = false;
    api
      .getSettings()
      .then((s) => {
        if (cancelled) return;
        const active = s.holdHotkeyEnabled
          ? s.holdHotkey
          : s.toggleHotkeyEnabled
            ? s.toggleHotkey
            : s.holdHotkey;
        setHotkeyDisplay(formatHotkeyForDisplay(active || FALLBACK_HOTKEY));
      })
      .catch(() => {
        // Keep fallback display
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <aside className="w-64 h-screen bg-sidebar flex flex-col border-r border-sidebar-border relative">
      {/* Logo Area */}
      <div className="p-6 pb-8">
        <img
          src="/light-logo.png"
          alt="Dictore"
          className="h-7 w-auto block dark:hidden"
        />
        <img
          src="/dark-logo.png"
          alt="Dictore"
          className="h-7 w-auto hidden dark:block"
        />
        <p className="text-xs text-cream-muted mt-2 font-mono">
          Local AI dictation
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-0.5">
        <p className="font-mono text-[10px] text-cream-muted/60 uppercase tracking-[0.2em] px-3 mb-2">
          navigate
        </p>
        {navItems.map((item) =>
          item.disabled ? (
            <div
              key={item.to}
              className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-cream-muted/40 cursor-not-allowed"
              title="Coming soon"
            >
              <item.icon className="h-4 w-4 text-cream-muted/30" strokeWidth={2} />
              <span className="flex-1">{item.label}</span>
              <span className="text-[9px] font-mono uppercase tracking-wider opacity-60">soon</span>
            </div>
          ) : (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/dashboard"}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-secondary text-cream"
                  : "text-cream-muted hover:text-cream hover:bg-secondary/60"
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  className={cn(
                    "h-4 w-4",
                    isActive ? "text-accent-500" : "text-cream-muted/70"
                  )}
                  strokeWidth={2}
                />
                <span className="flex-1">{item.label}</span>
                {isActive && (
                  <span className="w-1 h-1 rounded-full bg-accent-500" aria-hidden />
                )}
              </>
            )}
          </NavLink>
          )
        )}
      </nav>

      {/* Footer */}
      <div className="p-3 mt-auto space-y-1">

        {/* Pro Tip - terminal-style line, not a card */}
        <div className="px-3 py-2 text-xs text-cream-muted leading-relaxed font-mono border-l-2 border-accent-500/40 mb-3">
          <span className="text-cream-muted/60">{"→ "}</span>
          press{" "}
          <kbd className="text-accent-500 bg-accent-500/10 px-1 py-0.5 rounded text-[11px]">
            {hotkeyDisplay}
          </kbd>{" "}
          anywhere
        </div>

        {/* Community Links */}
        <button
          onClick={() => api.openExternalUrl(`${GITHUB_REPO_URL}/issues`)}
          className="flex items-center gap-2.5 px-3 py-2 w-full rounded-md text-xs text-cream-muted hover:text-cream hover:bg-secondary/60 transition-colors"
        >
          <MessageSquare className="h-3.5 w-3.5" strokeWidth={2} />
          Report issue
        </button>

        <button
          onClick={() => api.openExternalUrl(GITHUB_REPO_URL)}
          className="flex items-center gap-2.5 px-3 py-2 w-full rounded-md text-xs text-cream-muted hover:text-cream hover:bg-secondary/60 transition-colors"
        >
          <Github className="h-3.5 w-3.5" strokeWidth={2} />
          Star on GitHub
        </button>

        {/* Version footer */}
        <div className="pt-3 px-3 flex items-center justify-between text-[10px] text-cream-muted/50 font-mono">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-500" />
            v{APP_VERSION}
          </span>
          <span className="flex items-center gap-1">
            <Heart className="w-2.5 h-2.5" strokeWidth={2} />
            Open source
          </span>
        </div>
      </div>
    </aside>
  );
}
