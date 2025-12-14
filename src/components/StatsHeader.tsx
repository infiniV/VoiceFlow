import { useEffect, useState } from "react";
import { Flame, FileText, Type, Settings2, Languages, Cpu, Mic } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Stats } from "@/lib/types";
import HeroImg from "@/assets/hero-illustration.png";

type ConfigData = {
  model: string;
  language: string;
  micName: string;
}

export function StatsHeader() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [config, setConfig] = useState<ConfigData | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        // Load stats
        const statsData = await api.getStats();
        setStats(statsData);

        // Load config (settings + options to map IDs to names)
        const [settings, options] = await Promise.all([
          api.getSettings(),
          api.getOptions()
        ]);

        // Find mic name
        const currentMic = options.microphones.find(m => m.id === settings.microphone);
        const micName = settings.microphone === -1 ? "System Default" : (currentMic?.name || "Unknown Mic");

        setConfig({
          model: settings.model,
          language: settings.language,
          micName: micName
        });

      } catch (error) {
        console.error("Failed to load data:", error);
        setStats({ totalTranscriptions: 0, totalWords: 0, totalCharacters: 0, streakDays: 0 });
      }
    };
    load();
  }, []);

  if (!stats) {
    return <div className="animate-pulse h-48 rounded-xl bg-muted/20 w-full mb-8"></div>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      {/* Hero Card - Words */}
      <Card className="md:col-span-2 overflow-hidden relative border-none shadow-2xl bg-zinc-950 group">
        <div className="absolute inset-0 z-0 transition-transform duration-700 group-hover:scale-105">
            <img src={HeroImg} alt="Voice Flow" className="w-full h-full object-cover opacity-60" />
            <div className="absolute inset-0 bg-gradient-to-r from-zinc-950/95 via-zinc-950/50 to-transparent" />
        </div>
        
        {/* Animated Glow orb */}
        <div className="absolute top-[-50%] right-[-10%] w-[300px] h-[300px] bg-primary/20 rounded-full blur-[100px] pointer-events-none animate-pulse-slow" />

        <CardContent className="p-8 relative z-10 flex flex-col h-full justify-between">
            <div className="space-y-2">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 backdrop-blur-md w-fit">
                    <Type className="w-3.5 h-3.5 text-primary" /> 
                    <span className="text-xs font-medium text-zinc-300 uppercase tracking-wider">Total Words Dictated</span>
                </div>
                <h2 className="text-5xl md:text-6xl font-bold text-white tracking-tighter drop-shadow-lg">
                    {stats.totalWords.toLocaleString()}
                </h2>
            </div>
            
            <div className="mt-8 flex gap-4 flex-wrap">
                 <div className="flex items-center gap-3 bg-white/5 rounded-xl px-5 py-3 backdrop-blur-md border border-white/5 transition-all hover:bg-white/10 hover:border-white/20">
                    <div className="p-2 bg-primary/20 rounded-lg text-primary">
                        <Flame className="w-5 h-5" />
                    </div>
                    <div>
                        <p className="text-[10px] text-white/50 font-bold uppercase tracking-widest mb-0.5">Current Streak</p>
                        <p className="text-lg text-white font-bold leading-none">{stats.streakDays} <span className="text-sm font-normal text-white/50">days</span></p>
                    </div>
                 </div>
                 
                 <div className="flex items-center gap-3 bg-white/5 rounded-xl px-5 py-3 backdrop-blur-md border border-white/5 transition-all hover:bg-white/10 hover:border-white/20">
                    <div className="p-2 bg-blue-500/20 rounded-lg text-blue-400">
                        <FileText className="w-5 h-5" />
                    </div>
                    <div>
                        <p className="text-[10px] text-white/50 font-bold uppercase tracking-widest mb-0.5">Total Notes</p>
                        <p className="text-lg text-white font-bold leading-none">{stats.totalTranscriptions}</p>
                    </div>
                 </div>
            </div>
        </CardContent>
      </Card>
      
      {/* Active Configuration Card */}
      <Card className="bg-card/40 backdrop-blur-xl border-white/5 shadow-glass relative overflow-hidden flex flex-col">
        <div className="absolute top-0 right-0 p-20 bg-primary/5 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none" />
        
        <CardContent className="p-6 h-full flex flex-col relative z-10">
             <div className="flex items-center justify-between mb-6">
                 <div className="p-2.5 bg-primary/10 rounded-xl border border-primary/20">
                    <Settings2 className="w-5 h-5 text-primary" />
                 </div>
                 <span className="text-xs font-mono text-muted-foreground/60 bg-secondary/50 px-2 py-1 rounded">
                     Active Config
                 </span>
             </div>

             <div className="space-y-4 mt-auto">
                 {/* Model */}
                 <div className="group/item">
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wide flex items-center gap-1.5">
                            <Cpu className="w-3 h-3" /> Model
                        </span>
                    </div>
                    <div className="text-sm font-semibold text-foreground tracking-tight pl-4 border-l-2 border-primary/20 group-hover/item:border-primary transition-colors">
                        {config?.model ? (config.model.charAt(0).toUpperCase() + config.model.slice(1)) : "Loading..."}
                    </div>
                 </div>

                 {/* Language */}
                 <div className="group/item">
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wide flex items-center gap-1.5">
                            <Languages className="w-3 h-3" /> Language
                        </span>
                    </div>
                    <div className="text-sm font-semibold text-foreground tracking-tight pl-4 border-l-2 border-primary/20 group-hover/item:border-primary transition-colors">
                        {config?.language ? (config.language === "auto" ? "Auto-Detect" : config.language.toUpperCase()) : "Loading..."}
                    </div>
                 </div>

                 {/* Microphone */}
                 <div className="group/item">
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wide flex items-center gap-1.5">
                            <Mic className="w-3 h-3" /> Input
                        </span>
                    </div>
                    <div className="text-sm font-semibold text-foreground tracking-tight pl-4 border-l-2 border-primary/20 group-hover/item:border-primary transition-colors truncate" title={config?.micName}>
                        {config?.micName || "Loading..."}
                    </div>
                 </div>
             </div>
        </CardContent>
      </Card>
    </div>
  );
}
