"""
Database models and connection management
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import os


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize all database tables"""
        with self.get_connection() as conn:
            # Jobs table (simplified - no chunk tracking)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    duration_seconds REAL,

                    status TEXT NOT NULL DEFAULT 'pending',

                    model_size TEXT NOT NULL DEFAULT 'voxtral-mini-latest',
                    language TEXT,
                    enable_diarization INTEGER NOT NULL DEFAULT 1,
                    num_speakers INTEGER,

                    error_message TEXT,

                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL
                )
            """)

            # Transcripts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    job_id TEXT PRIMARY KEY,

                    full_text TEXT,
                    segments_json TEXT,

                    language TEXT,
                    language_probability REAL,

                    num_speakers INTEGER,
                    diarization_json TEXT,

                    word_count INTEGER,
                    duration_seconds REAL,

                    created_at TEXT NOT NULL,

                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
            """)

            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC)")

            conn.commit()

    @contextmanager
    def get_connection(self):
        """Get a database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def create_job(
        self,
        job_id: str,
        filename: str,
        original_path: str,
        file_size: int,
        duration_seconds: Optional[float] = None,
        model_size: str = "voxtral-mini-latest",
        language: Optional[str] = None,
        enable_diarization: bool = True,
        num_speakers: Optional[int] = None
    ) -> Dict:
        """Create a new transcription job"""
        now = datetime.utcnow().isoformat()

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    id, filename, original_path, file_size, duration_seconds,
                    status, model_size, language, enable_diarization, num_speakers,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """, (
                job_id, filename, original_path, file_size, duration_seconds,
                model_size, language, 1 if enable_diarization else 0, num_speakers,
                now, now
            ))
            conn.commit()

        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get a job by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['enable_diarization'] = bool(result['enable_diarization'])
                return result
            return None

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """List jobs with optional filtering"""
        with self.get_connection() as conn:
            if status:
                cursor = conn.execute("""
                    SELECT * FROM jobs
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (status, limit, offset))
            else:
                cursor = conn.execute("""
                    SELECT * FROM jobs
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))

            jobs = []
            for row in cursor.fetchall():
                job = dict(row)
                job['enable_diarization'] = bool(job['enable_diarization'])
                jobs.append(job)
            return jobs

    def update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
    ):
        """Update job status"""
        now = datetime.utcnow().isoformat()

        updates = ["status = ?", "updated_at = ?"]
        params: List[Any] = [status, now]

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if status == 'transcribing':
            updates.append("started_at = COALESCE(started_at, ?)")
            params.append(now)

        if status == 'completed':
            updates.append("completed_at = ?")
            params.append(now)

        params.append(job_id)

        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()

    def delete_job(self, job_id: str):
        """Delete a job and its related data"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM transcripts WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()

    def save_transcript(
        self,
        job_id: str,
        full_text: str,
        segments: List[Dict],
        language: str,
        language_probability: float,
        num_speakers: Optional[int] = None,
        diarization: Optional[List[Dict]] = None
    ):
        """Save final transcript"""
        now = datetime.utcnow().isoformat()
        duration = segments[-1]['end'] if segments else 0

        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO transcripts (
                    job_id, full_text, segments_json, language, language_probability,
                    num_speakers, diarization_json, word_count, duration_seconds, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                full_text,
                json.dumps(segments),
                language,
                language_probability,
                num_speakers,
                json.dumps(diarization) if diarization else None,
                len(full_text.split()),
                duration,
                now
            ))
            conn.commit()

    def get_transcript(self, job_id: str) -> Optional[Dict]:
        """Get transcript for a job"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM transcripts WHERE job_id = ?", (job_id,)
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['segments'] = json.loads(result['segments_json']) if result['segments_json'] else []
                result['diarization'] = json.loads(result['diarization_json']) if result['diarization_json'] else None
                del result['segments_json']
                del result['diarization_json']
                return result
            return None
