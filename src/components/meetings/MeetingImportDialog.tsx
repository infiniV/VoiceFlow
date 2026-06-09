/* Import an existing audio file as a Recording. The Pyloid backend resolves
   the path to its data folder and copies/converts as needed. */

import { useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

interface MeetingImportDialogProps {
  open: boolean;
  onOpenChange(open: boolean): void;
  onImported(recordingId: number): void;
}

export function MeetingImportDialog({
  open,
  onOpenChange,
  onImported,
}: MeetingImportDialogProps) {
  const [filePath, setFilePath] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!filePath.trim()) return;
    setBusy(true);
    try {
      const { recording_id } = await api.recordingsImportFile(
        filePath.trim(),
        title.trim() || undefined,
      );
      toast.success("Audio imported");
      onImported(recording_id);
      onOpenChange(false);
      setFilePath("");
      setTitle("");
    } catch (err) {
      console.error("Import failed", err);
      toast.error("Could not import audio");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cream-muted/60">
            new recording
          </p>
          <DialogTitle className="font-display text-xl font-medium tracking-tight text-cream">
            Import audio
          </DialogTitle>
          <DialogDescription className="text-sm text-cream-muted leading-relaxed">
            Paste an absolute path to a WAV, MP3, or FLAC file on your machine.
            Dictore will copy it into your recordings library and transcribe
            it in the background.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label
              htmlFor="import-path"
              className="text-sm font-medium text-cream"
            >
              File path
            </Label>
            <Input
              id="import-path"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="/home/you/Downloads/meeting.wav"
              required
              autoFocus
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label
              htmlFor="import-title"
              className="text-sm font-medium text-cream"
            >
              Title <span className="text-cream-muted/60 font-normal">(optional)</span>
            </Label>
            <Input
              id="import-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Weekly sync"
            />
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={busy || !filePath.trim()}>
              {busy ? "Importing…" : "Import"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
