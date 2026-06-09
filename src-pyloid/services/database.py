import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from services.logger import debug


_RECORDING_UPDATABLE_FIELDS = frozenset({"title", "summary", "notes", "tags", "language"})


class DatabaseService:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            app_data = Path.home() / ".Dictore"
            app_data.mkdir(exist_ok=True)
            db_path = app_data / "Dictore.db"

        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        # timeout=5.0 + busy_timeout=5000 means SQLite returns SQLITE_BUSY
        # after 5s of lock contention instead of blocking the asyncio RPC
        # thread indefinitely. RPC handlers like get_history / get_stats are
        # `async def` but call sync sqlite synchronously — without a timeout,
        # a long-held write lock from another connection could wedge the
        # whole HTTP RPC server.
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # History table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                word_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Add audio attachment columns if they don't exist (lightweight migration)
        self._ensure_history_audio_columns(cursor)

        # Recordings (Meetings feature)
        self._ensure_recordings_tables(cursor)

        conn.commit()
        conn.close()

    def _ensure_recordings_tables(self, cursor: sqlite3.Cursor) -> None:
        """Create recordings + recording_segments tables (idempotent)."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                audio_relpath TEXT,
                audio_duration_ms INTEGER,
                audio_size_bytes INTEGER,
                audio_sample_rate INTEGER,
                audio_channels INTEGER,
                sources TEXT NOT NULL DEFAULT '[]',
                language TEXT,
                transcript TEXT,
                transcript_model TEXT,
                transcript_status TEXT NOT NULL DEFAULT 'pending',
                transcript_progress REAL NOT NULL DEFAULT 0,
                transcript_error TEXT,
                summary TEXT,
                summary_provider TEXT,
                summary_status TEXT NOT NULL DEFAULT 'idle',
                summary_progress REAL NOT NULL DEFAULT 0,
                summary_error TEXT,
                tags TEXT NOT NULL DEFAULT '[]',
                notes TEXT,
                recorder_state TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_recordings_created_at "
            "ON recordings(created_at DESC)"
        )

        # Migration for existing DBs: add transcript_model column if missing.
        cursor.execute("PRAGMA table_info(recordings)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "transcript_model" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE recordings ADD COLUMN transcript_model TEXT")
                debug("Added transcript_model column to recordings table")
            except sqlite3.OperationalError as exc:
                debug(f"Failed to add transcript_model column: {exc}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recording_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recording_id INTEGER NOT NULL,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY(recording_id) REFERENCES recordings(id) ON DELETE CASCADE
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_recording_segments_recording "
            "ON recording_segments(recording_id)"
        )

    def _ensure_history_audio_columns(self, cursor: sqlite3.Cursor) -> None:
        """Ensure audio attachment columns exist on history (idempotent)."""
        columns = {
            "audio_relpath": "TEXT",
            "audio_duration_ms": "INTEGER",
            "audio_size_bytes": "INTEGER",
            "audio_mime": "TEXT"
        }

        cursor.execute("PRAGMA table_info(history)")
        existing = {row[1] for row in cursor.fetchall()}

        for name, col_type in columns.items():
            if name not in existing:
                try:
                    cursor.execute(f"ALTER TABLE history ADD COLUMN {name} {col_type}")
                    debug(f"Added column {name} to history table")
                except sqlite3.OperationalError as exc:
                    debug(f"Failed to add column {name}: {exc}")

    # Settings methods
    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()
        conn.close()

    def get_all_settings(self) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        conn.close()
        return {row["key"]: row["value"] for row in rows}

    # History methods
    def add_history(
        self,
        text: str,
        audio_relpath: Optional[str] = None,
        audio_duration_ms: Optional[int] = None,
        audio_size_bytes: Optional[int] = None,
        audio_mime: Optional[str] = None,
    ) -> int:
        char_count = len(text)
        word_count = len(text.split())
        created_at = datetime.now().isoformat()

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO history (
                   text, char_count, word_count, created_at,
                   audio_relpath, audio_duration_ms, audio_size_bytes, audio_mime
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                text,
                char_count,
                word_count,
                created_at,
                audio_relpath,
                audio_duration_ms,
                audio_size_bytes,
                audio_mime,
            )
        )
        history_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return history_id

    def update_history_audio(
        self,
        history_id: int,
        audio_relpath: str,
        audio_duration_ms: Optional[int],
        audio_size_bytes: Optional[int],
        audio_mime: Optional[str] = None,
    ) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE history
            SET audio_relpath = ?, audio_duration_ms = ?, audio_size_bytes = ?, audio_mime = ?
            WHERE id = ?
            """,
            (audio_relpath, audio_duration_ms, audio_size_bytes, audio_mime, history_id),
        )
        conn.commit()
        conn.close()

    def get_history(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str = None,
        include_audio_meta: bool = False,
    ) -> list:
        """Fetch history entries, optionally including audio metadata."""
        conn = self._get_connection()
        cursor = conn.cursor()

        base_query = """
            SELECT
                id,
                text,
                char_count,
                word_count,
                created_at,
                audio_relpath,
                audio_duration_ms,
                audio_size_bytes,
                audio_mime,
                CASE WHEN audio_relpath IS NOT NULL THEN 1 ELSE 0 END AS has_audio
            FROM history
        """

        params = []
        if search:
            base_query += " WHERE text LIKE ?"
            params.append(f"%{search}%")

        base_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(base_query, params)
        rows = cursor.fetchall()
        conn.close()

        entries = [dict(row) for row in rows]
        for entry in entries:
            entry["has_audio"] = bool(entry.get("has_audio"))

        if not include_audio_meta:
            for entry in entries:
                # Remove heavy meta unless explicitly requested
                entry.pop("audio_duration_ms", None)
                entry.pop("audio_size_bytes", None)
                entry.pop("audio_mime", None)
                entry.pop("audio_relpath", None)
        return entries

    def get_history_entry(self, history_id: int) -> Optional[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
                text,
                char_count,
                word_count,
                created_at,
                audio_relpath,
                audio_duration_ms,
                audio_size_bytes,
                audio_mime
            FROM history
            WHERE id = ?
            """,
            (history_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def delete_history(self, history_id: int):
        entry = self.get_history_entry(history_id)

        if entry and entry.get("audio_relpath"):
            self._delete_audio_file(entry["audio_relpath"])

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history WHERE id = ?", (history_id,))
        conn.commit()
        conn.close()

    def clear_old_history(self, days: int):
        """Clear history older than specified days. -1 means keep forever."""
        if days < 0:
            return

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        conn = self._get_connection()
        cursor = conn.cursor()

        # Collect audio paths before deletion
        cursor.execute(
            "SELECT audio_relpath FROM history WHERE created_at < ? AND audio_relpath IS NOT NULL",
            (cutoff,),
        )
        rows = cursor.fetchall()
        for row in rows:
            self._delete_audio_file(row["audio_relpath"])

        cursor.execute("DELETE FROM history WHERE created_at < ?", (cutoff,))
        conn.commit()
        conn.close()

    def get_stats(self) -> dict:
        """Get aggregate stats from history."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get totals
        cursor.execute("""
            SELECT
                COUNT(*) as total_transcriptions,
                COALESCE(SUM(word_count), 0) as total_words,
                COALESCE(SUM(char_count), 0) as total_characters
            FROM history
        """)
        row = cursor.fetchone()

        # Calculate streak (consecutive days with transcriptions)
        cursor.execute("""
            SELECT DISTINCT DATE(created_at) as day
            FROM history
            ORDER BY day DESC
        """)
        days = [r["day"] for r in cursor.fetchall()]
        streak = self._calculate_streak(days)

        conn.close()
        result = {
            "totalTranscriptions": int(row["total_transcriptions"]),
            "totalWords": int(row["total_words"]),
            "totalCharacters": int(row["total_characters"]),
            "streakDays": streak,
        }
        debug(f"Database get_stats: {result}")
        return result

    def reset_all_data(self):
        """Delete all data and reset to fresh state."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear all history
        cursor.execute("DELETE FROM history")

        # Clear all settings (will use defaults on next load)
        cursor.execute("DELETE FROM settings")

        conn.commit()
        conn.close()
        debug("All data has been reset")

        # Remove audio files
        audio_dir = self.db_path.parent / "audio"
        if audio_dir.exists():
            for file in audio_dir.glob("*"):
                try:
                    file.unlink()
                except Exception as exc:
                    debug(f"Failed to delete audio file during reset: {exc}")

    def _calculate_streak(self, days: list) -> int:
        """Calculate consecutive days streak from list of date strings."""
        if not days:
            return 0

        from datetime import datetime, timedelta

        streak = 0
        today = datetime.now().date()

        for i, day_str in enumerate(days):
            day = datetime.strptime(day_str, "%Y-%m-%d").date()
            expected = today - timedelta(days=i)

            # Allow for today or yesterday to start the streak
            if i == 0 and (day == today or day == today - timedelta(days=1)):
                streak = 1
                if day == today - timedelta(days=1):
                    expected = today - timedelta(days=1)
            elif day == expected:
                streak += 1
            else:
                break

        return streak

    # ------------------------------------------------------------------ Recordings (Meetings)

    def create_recording(self, title: str, sources: list[str]) -> int:
        now = datetime.now().isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO recordings (title, sources, created_at, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (title, json.dumps(sources), now, now),
            )
            rid = cursor.lastrowid
            conn.commit()
            return rid
        finally:
            conn.close()

    def get_recording(self, recording_id: int, include_segments: bool = False) -> Optional[dict]:
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM recordings WHERE id = ?", (recording_id,)
            ).fetchone()
            if row is None:
                return None
            rec = self._row_to_recording(row)
            if include_segments:
                seg_rows = conn.execute(
                    """SELECT id, recording_id, start_ms, end_ms, text
                       FROM recording_segments
                       WHERE recording_id = ?
                       ORDER BY start_ms ASC, id ASC""",
                    (recording_id,),
                ).fetchall()
                rec["segments"] = [dict(r) for r in seg_rows]
            return rec
        finally:
            conn.close()

    def list_recordings(
        self,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> list[dict]:
        conn = self._get_connection()
        try:
            query = "SELECT * FROM recordings"
            params: list = []
            if search:
                query += " WHERE title LIKE ?"
                params.append(f"%{search}%")
            query += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_recording(r) for r in rows]
        finally:
            conn.close()

    def update_recording(self, recording_id: int, **fields) -> None:
        unknown = set(fields) - _RECORDING_UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"unknown recording fields: {sorted(unknown)}")
        if not fields:
            return
        sets, params = [], []
        for name, value in fields.items():
            if name == "tags":
                value = json.dumps(value or [])
            sets.append(f"{name} = ?")
            params.append(value)
        sets.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(recording_id)

        conn = self._get_connection()
        try:
            conn.execute(
                f"UPDATE recordings SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
        finally:
            conn.close()

    def set_recording_audio(
        self,
        recording_id: int,
        audio_relpath: str,
        duration_ms: Optional[int],
        size_bytes: Optional[int],
        sample_rate: Optional[int],
        channels: Optional[int],
    ) -> None:
        conn = self._get_connection()
        try:
            conn.execute(
                """UPDATE recordings
                   SET audio_relpath = ?, audio_duration_ms = ?, audio_size_bytes = ?,
                       audio_sample_rate = ?, audio_channels = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    audio_relpath, duration_ms, size_bytes,
                    sample_rate, channels, datetime.now().isoformat(),
                    recording_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def set_recording_recorder_state(self, recording_id: int, state: Optional[str]) -> None:
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE recordings SET recorder_state = ?, updated_at = ? WHERE id = ?",
                (state, datetime.now().isoformat(), recording_id),
            )
            conn.commit()
        finally:
            conn.close()

    def update_transcript_status(
        self,
        recording_id: int,
        status: str,
        progress: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        sets = ["transcript_status = ?", "updated_at = ?"]
        params: list = [status, datetime.now().isoformat()]
        if progress is not None:
            sets.insert(1, "transcript_progress = ?")
            params.insert(1, progress)
        if error is not None:
            sets.insert(-1, "transcript_error = ?")
            params.insert(-1, error)
        params.append(recording_id)
        conn = self._get_connection()
        try:
            conn.execute(
                f"UPDATE recordings SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
        finally:
            conn.close()

    def update_summary_status(
        self,
        recording_id: int,
        status: str,
        progress: Optional[float] = None,
        error: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> None:
        sets = ["summary_status = ?", "updated_at = ?"]
        params: list = [status, datetime.now().isoformat()]
        if progress is not None:
            sets.insert(1, "summary_progress = ?")
            params.insert(1, progress)
        if error is not None:
            sets.insert(-1, "summary_error = ?")
            params.insert(-1, error)
        if provider is not None:
            sets.insert(-1, "summary_provider = ?")
            params.insert(-1, provider)
        params.append(recording_id)
        conn = self._get_connection()
        try:
            conn.execute(
                f"UPDATE recordings SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
        finally:
            conn.close()

    def set_recording_transcript(
        self,
        recording_id: int,
        transcript: str,
        language: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """Persist the final transcript text. Segments go via replace_recording_segments.

        `model` is the whisper model name that produced the transcript (e.g.
        'tiny', 'large-v3'). Optional and backward-compatible — existing callers
        that don't pass it leave the column NULL or unchanged on re-transcribe.
        """
        conn = self._get_connection()
        try:
            conn.execute(
                """UPDATE recordings
                   SET transcript = ?,
                       language = COALESCE(?, language),
                       transcript_model = COALESCE(?, transcript_model),
                       updated_at = ?
                   WHERE id = ?""",
                (transcript, language, model, datetime.now().isoformat(), recording_id),
            )
            conn.commit()
        finally:
            conn.close()

    def replace_recording_segments(self, recording_id: int, segments: list[dict]) -> None:
        conn = self._get_connection()
        try:
            conn.execute(
                "DELETE FROM recording_segments WHERE recording_id = ?", (recording_id,)
            )
            if segments:
                conn.executemany(
                    """INSERT INTO recording_segments (recording_id, start_ms, end_ms, text)
                       VALUES (?, ?, ?, ?)""",
                    [
                        (recording_id, int(s["start_ms"]), int(s["end_ms"]), str(s["text"]))
                        for s in segments
                    ],
                )
            conn.commit()
        finally:
            conn.close()

    def delete_recording(self, recording_id: int) -> None:
        # Capture the audio path so the caller can delete the file off disk.
        rec = self.get_recording(recording_id)
        if rec and rec.get("audio_relpath"):
            self._delete_audio_file(rec["audio_relpath"])
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
            conn.commit()
        finally:
            conn.close()

    def list_unfinished_recordings(self) -> list[dict]:
        """Recordings that were left mid-flight (used by crash-recovery on startup)."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM recordings WHERE recorder_state IS NOT NULL "
                "ORDER BY created_at ASC"
            ).fetchall()
            return [self._row_to_recording(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def _row_to_recording(row: sqlite3.Row) -> dict:
        rec = dict(row)
        rec["sources"] = json.loads(rec.get("sources") or "[]")
        rec["tags"] = json.loads(rec.get("tags") or "[]")
        return rec

    def _delete_audio_file(self, relpath: str) -> None:
        """Delete an audio file, ignoring missing files."""
        try:
            data_dir = self.db_path.parent.resolve()
            audio_root = (data_dir / "audio").resolve()
            path = (data_dir / relpath).resolve()
            try:
                path.relative_to(audio_root)
            except ValueError:
                return
            if path.exists():
                path.unlink()
        except Exception as exc:
            debug(f"Failed to delete audio file {relpath}: {exc}")
