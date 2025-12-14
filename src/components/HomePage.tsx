import { useEffect, useState } from "react";
import { Copy, Trash2, Clock, CalendarDays, Search } from "lucide-react";
import EmptyStateImg from "@/assets/empty-state.png";
import { toast } from "sonner";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatsHeader } from "@/components/StatsHeader";
import { api } from "@/lib/api";
import type { HistoryEntry } from "@/lib/types";
import { Input } from "@/components/ui/input";

export function HomePage() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        const data = await api.getHistory(50, 0); // Load more items for the grid
        setHistory(data);
      } catch (error) {
        console.error("Failed to load history:", error);
        setError("Failed to load history. Please try again.");
        toast.error("Failed to load history");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleCopy = async (text: string) => {
    try {
      await api.copyToClipboard(text);
      toast.success("Copied to clipboard");
    } catch (error) {
      try {
        await navigator.clipboard.writeText(text);
        toast.success("Copied to clipboard");
      } catch {
        toast.error("Failed to copy to clipboard");
      }
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteHistory(id);
      setHistory((prev) => prev.filter((h) => h.id !== id));
      toast.success("Transcription deleted");
    } catch (error) {
      console.error("Failed to delete:", error);
      toast.error("Failed to delete transcription");
    }
  };

  const filteredHistory = history.filter(entry => 
    entry.text.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const groupedHistory = groupByDate(filteredHistory);

  return (
    <div className="min-h-screen w-full bg-background/50">
      <div className="w-full max-w-[1600px] mx-auto p-6 md:p-10 space-y-10">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 animate-in fade-in slide-in-from-top-4 duration-500">
          <div>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tighter text-foreground mb-2">
              Dashboard
            </h1>
            <p className="text-lg text-muted-foreground/80 font-light max-w-2xl">
              Your voice, organized. Manage your recent transcriptions and insights.
            </p>
          </div>
          <div className="w-full md:w-auto">
             <div className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                <Input 
                  placeholder="Search transcriptions..." 
                  className="pl-10 w-full md:w-[300px] bg-background/50 border-border/50 focus:bg-background transition-all"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
             </div>
          </div>
        </div>

        {/* Stats / Hero Section */}
        <section className="animate-in fade-in slide-in-from-top-6 duration-700 delay-100">
          <StatsHeader />
        </section>

        {/* Recent History Grid */}
        <section className="space-y-8 animate-in fade-in slide-in-from-top-8 duration-700 delay-200">
          <div className="flex items-center justify-between border-b border-border/40 pb-4">
            <h2 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
              <Clock className="w-5 h-5 text-primary" />
              Recent History
            </h2>
            <span className="text-sm text-muted-foreground font-mono bg-secondary/50 px-3 py-1 rounded-full">
              {filteredHistory.length} entries
            </span>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
               {[...Array(6)].map((_, i) => (
                 <div key={i} className="h-48 rounded-xl bg-secondary/20 animate-pulse" />
               ))}
            </div>
          ) : error ? (
            <div className="text-center py-20 border border-dashed border-destructive/20 rounded-2xl bg-destructive/5">
              <p className="text-destructive font-medium mb-4">{error}</p>
              <Button variant="outline" onClick={() => window.location.reload()}>
                Try again
              </Button>
            </div>
          ) : Object.keys(groupedHistory).length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center space-y-6 border border-dashed border-border/50 rounded-3xl bg-secondary/5">
               <img 
                 src={EmptyStateImg} 
                 alt="No transcriptions" 
                 className="w-64 opacity-80 mix-blend-luminosity hover:mix-blend-normal hover:scale-105 transition-all duration-500" 
               />
               <div className="space-y-2">
                 <p className="text-xl font-medium text-foreground">No transcriptions found</p>
                 <p className="text-muted-foreground">
                   {searchQuery ? "Try adjusting your search terms." : "Press Ctrl+Win to start your first dictation."}
                 </p>
               </div>
            </div>
          ) : (
            <div className="space-y-10">
              {Object.entries(groupedHistory).map(([dateLabel, entries]) => (
                <div key={dateLabel} className="space-y-4">
                  <div className="flex items-center gap-3 sticky top-0 z-10 bg-background/95 backdrop-blur py-3">
                    <CalendarDays className="w-4 h-4 text-muted-foreground" />
                    <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground">
                      {dateLabel}
                    </h3>
                    <div className="h-px flex-1 bg-border/40" />
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                    {entries.map((entry) => (
                      <Card
                        key={entry.id}
                        className="group flex flex-col justify-between h-full bg-card/50 backdrop-blur-sm border-border/50 hover:bg-card hover:border-primary/20 hover:shadow-xl hover:-translate-y-1 transition-all duration-300"
                      >
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                          <span className="text-xs font-mono text-muted-foreground bg-secondary/50 px-2 py-1 rounded">
                             {formatTime(entry.created_at)}
                          </span>
                          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                             <Button
                               variant="ghost"
                               size="icon-sm"
                               className="h-7 w-7 text-muted-foreground hover:text-primary hover:bg-primary/10"
                               onClick={() => handleCopy(entry.text)}
                             >
                                <Copy className="h-3.5 w-3.5" />
                             </Button>
                             <Button
                               variant="ghost"
                               size="icon-sm"
                               className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                               onClick={() => handleDelete(entry.id)}
                             >
                                <Trash2 className="h-3.5 w-3.5" />
                             </Button>
                          </div>
                        </CardHeader>
                        <CardContent className="pt-2 flex-grow">
                          <p className="text-base leading-relaxed line-clamp-4 font-medium text-foreground/90 group-hover:text-foreground transition-colors">
                            {entry.text}
                          </p>
                        </CardContent>
                        <div className="px-6 pb-4 pt-0">
                           <div className="text-[10px] uppercase tracking-wider font-semibold text-primary/40 group-hover:text-primary/80 transition-colors">
                              {entry.word_count} words
                           </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function groupByDate(entries: HistoryEntry[]): Record<string, HistoryEntry[]> {
  const groups: Record<string, HistoryEntry[]> = {};
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  for (const entry of entries) {
    const entryDate = new Date(entry.created_at);
    let label: string;

    if (isSameDay(entryDate, today)) {
      label = "Today";
    } else if (isSameDay(entryDate, yesterday)) {
      label = "Yesterday";
    } else {
      label = entryDate.toLocaleDateString([], { weekday: 'long', month: "long", day: "numeric" });
    }

    if (!groups[label]) {
      groups[label] = [];
    }
    groups[label].push(entry);
  }

  return groups;
}

function isSameDay(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
}
