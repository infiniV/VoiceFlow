import { NavLink } from "react-router-dom";
import { Mic, Home, History, Settings, Sparkles, Github, Heart, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const GITHUB_REPO_URL = "https://github.com/infiniV/VoiceFlow";

const navItems = [
  { to: "/dashboard", icon: Home, label: "Home" },
  { to: "/dashboard/history", icon: History, label: "History" },
  { to: "/dashboard/settings", icon: Settings, label: "Settings" },
];

interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <aside className="w-64 h-screen bg-sidebar flex flex-col border-r border-sidebar-border relative overflow-hidden">
      {/* Animated gradient orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="orb orb-primary w-[200px] h-[200px] -top-20 -left-20 opacity-40" />
        <div className="orb orb-accent w-[150px] h-[150px] bottom-40 -right-20 opacity-30" />
      </div>

      {/* Logo Area */}
      <div className="p-6 pb-8 relative z-10">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 bg-gradient-to-br from-primary via-primary/90 to-emerald-600 rounded-xl flex items-center justify-center shadow-lg shadow-primary/25 ring-1 ring-white/10">
            <Mic className="h-5 w-5 text-primary-foreground" />
          </div>
          <div>
            <h1 className="font-semibold text-lg text-sidebar-foreground tracking-tight leading-none">
              Voice<span className="headline-serif text-primary">Flow</span>
            </h1>
            <p className="text-xs text-sidebar-foreground/50 font-medium mt-1 tracking-wide">
              Local AI Dictation
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 space-y-1.5 relative z-10">
        <p className="text-[10px] font-semibold text-sidebar-foreground/40 uppercase tracking-widest px-4 mb-3">
          Navigate
        </p>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/dashboard"}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "group flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-300",
                isActive
                  ? "glass-strong text-primary shadow-lg shadow-primary/10"
                  : "text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 hover:pl-5 border border-transparent"
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  className={cn(
                    "h-4 w-4 transition-all duration-300",
                    isActive ? "text-primary" : "text-sidebar-foreground/50 group-hover:text-primary"
                  )}
                />
                <span className="flex-1">{item.label}</span>
                {isActive && (
                  <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Promo / Footer */}
      <div className="p-4 mt-auto relative z-10 space-y-4">

        {/* Pro Tip Card */}
        <div className="glass-card p-4 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary/10 rounded-full blur-2xl -mr-8 -mt-8 transition-all group-hover:bg-primary/20" />
          <div className="relative z-10">
            <div className="flex items-center gap-2 mb-3">
              <div className="p-1.5 rounded-lg bg-primary/20 text-primary">
                <Sparkles className="w-3.5 h-3.5" />
              </div>
              <span className="text-xs font-semibold text-sidebar-foreground/80 uppercase tracking-wider">Pro Tip</span>
            </div>
            <p className="text-xs text-sidebar-foreground/60 leading-relaxed">
              Press{" "}
              <kbd className="text-primary font-semibold font-mono bg-primary/10 px-1.5 py-0.5 rounded border border-primary/20">
                Ctrl+Win
              </kbd>{" "}
              anywhere to start dictating.
            </p>
          </div>
        </div>

        {/* Community Links */}
        <div className="space-y-1">
          <button
            onClick={() => api.openExternalUrl(`${GITHUB_REPO_URL}/issues`)}
            className="flex items-center gap-3 px-4 py-2.5 w-full rounded-xl text-xs font-medium text-sidebar-foreground/60 hover:text-primary hover:bg-primary/5 transition-all border border-transparent hover:border-primary/10"
          >
            <MessageSquare className="h-4 w-4" />
            Report Issue
          </button>

          <button
            onClick={() => api.openExternalUrl(GITHUB_REPO_URL)}
            className="flex items-center gap-3 px-4 py-2.5 w-full rounded-xl text-xs font-medium text-sidebar-foreground/60 hover:text-primary hover:bg-primary/5 transition-all border border-transparent hover:border-primary/10"
          >
            <Github className="h-4 w-4" />
            Star on GitHub
          </button>

          {/* Footer info */}
          <div className="pt-3 px-4 flex items-center justify-between text-[10px] text-sidebar-foreground/30 font-mono">
            <span className="badge-glow !p-1.5 !text-[10px]">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              v1.3.1
            </span>
            <span className="flex items-center gap-1">
              <Heart className="w-2.5 h-2.5 text-red-500/60" />
              Open Source
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
