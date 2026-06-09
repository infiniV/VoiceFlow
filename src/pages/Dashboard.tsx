import { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Menu } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { BottomTabBar } from "@/components/BottomTabBar";
import { HomePage } from "@/components/HomePage";
import { HistoryPage } from "@/components/HistoryPage";
import { SettingsTab } from "@/components/SettingsTab";
import { MeetingsListPage } from "@/components/meetings/MeetingsListPage";
import { MeetingRecorderPage } from "@/components/meetings/MeetingRecorderPage";
import { MeetingDetailPage } from "@/components/meetings/MeetingDetailPage";
import { MeetingRecorderProvider } from "@/components/meetings/MeetingRecorderContext";
import { HotkeyStatusBanner } from "@/components/HotkeyStatusBanner";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";

export function Dashboard() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <MeetingRecorderProvider>
    <div className="flex h-screen bg-background">
      <div className="hidden md:block">
        <Sidebar />
      </div>

      <header className="md:hidden fixed top-0 left-0 right-0 z-40 h-14 bg-sidebar border-b border-sidebar-border px-4 flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="text-cream"
          onClick={() => setMobileMenuOpen(true)}
          aria-label="Open navigation menu"
          aria-expanded={mobileMenuOpen}
          aria-controls="mobile-navigation-sheet"
        >
          <Menu className="h-5 w-5" />
        </Button>
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
      </header>

      <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <SheetContent
          id="mobile-navigation-sheet"
          side="left"
          className="p-0 w-64 bg-sidebar border-sidebar-border"
        >
          <SheetTitle className="sr-only">Navigation Menu</SheetTitle>
          <SheetDescription className="sr-only">
            Move between sections of Dictore — Record, Meetings, History, and Settings.
          </SheetDescription>
          <Sidebar onNavigate={() => setMobileMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Banner sits in the right column above main so the hotkey warning stays pinned and doesn't scroll with content */}
      <div className="flex-1 flex flex-col min-w-0 pt-14 md:pt-0">
        <HotkeyStatusBanner />
        <main className="flex-1 overflow-auto pb-16 md:pb-0">
          <Routes>
            <Route index element={<HomePage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="meetings" element={<MeetingsListPage />} />
            <Route path="meetings/record" element={<MeetingRecorderPage />} />
            <Route path="meetings/:id" element={<MeetingDetailPage />} />
            <Route path="settings" element={<SettingsTab />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
        <BottomTabBar />
      </div>
    </div>
    </MeetingRecorderProvider>
  );
}
