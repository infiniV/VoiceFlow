import { NavLink, useLocation } from "react-router-dom";
import { Mic, Radio, History, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { MiniWaveform } from "@/components/RecordingOrb";

const tabs = [
  { to: "/dashboard", icon: Mic, label: "Record", end: true },
  { to: "/dashboard/meetings", icon: Radio, label: "Meetings", end: false },
  { to: "/dashboard/history", icon: History, label: "History", end: false },
  { to: "/dashboard/settings", icon: Settings, label: "Settings", end: false },
];

interface BottomTabBarProps {
  isRecording?: boolean;
}

export function BottomTabBar({ isRecording = false }: BottomTabBarProps) {
  const location = useLocation();

  return (
    <nav
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-background/95 backdrop-blur-md pb-[env(safe-area-inset-bottom)]"
      aria-label="Main navigation"
    >
      <div className="flex items-stretch">
        {tabs.map((tab) => {
          const isActive = tab.end
            ? location.pathname === tab.to
            : location.pathname.startsWith(tab.to);

          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className="flex-1 flex flex-col items-center justify-center gap-1 py-2 min-h-[56px] transition-colors"
            >
              <span
                className={cn(
                  "h-6 flex items-center justify-center",
                  isActive ? "text-accent-500" : "text-cream-muted/60"
                )}
              >
                {tab.to === "/dashboard" && isRecording ? (
                  <MiniWaveform isActive />
                ) : (
                  <tab.icon
                    className="h-5 w-5"
                    strokeWidth={isActive ? 2.5 : 2}
                  />
                )}
              </span>
              <span
                className={cn(
                  "text-[10px] font-medium tracking-wide",
                  isActive ? "text-accent-500 font-semibold" : "text-cream-muted/60"
                )}
              >
                {tab.label}
              </span>
              <span
                className={cn(
                  "w-1 h-1 rounded-full",
                  isActive ? "bg-accent-500" : "bg-transparent"
                )}
                aria-hidden
              />
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}
