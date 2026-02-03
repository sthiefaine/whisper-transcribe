"""
Checkpoint Manager
Handles saving and restoring transcription progress
"""
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
import sqlite3


@dataclass
class ChunkCheckpoint:
    chunk_index: int
    status: str  # 'pending', 'processing', 'completed', 'failed'
    file_path: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    transcript_segments: Optional[List[Dict]] = None
    language: Optional[str] = None
    language_probability: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class JobCheckpoint:
    job_id: str
    audio_path: str
    total_chunks: int
    chunk_duration: int
    model_size: str
    language: Optional[str]
    enable_diarization: bool
    created_at: str
    updated_at: str
    status: str  # 'pending', 'chunking', 'transcribing', 'diarizing', 'merging', 'completed', 'failed'
    current_chunk_index: int
    chunks: List[ChunkCheckpoint] = field(default_factory=list)
    diarization_completed: bool = False
    diarization_segments: Optional[List[Dict]] = None
    num_speakers: Optional[int] = None
    merged_transcript: Optional[Dict] = None


class CheckpointManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize checkpoint tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_checkpoints (
                    job_id TEXT PRIMARY KEY,
                    checkpoint_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_checkpoint(self, checkpoint: JobCheckpoint):
        """Save or update job checkpoint"""
        checkpoint.updated_at = datetime.utcnow().isoformat()

        # Convert to dict, handling nested dataclasses
        data = asdict(checkpoint)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO job_checkpoints
                (job_id, checkpoint_data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (
                checkpoint.job_id,
                json.dumps(data),
                checkpoint.created_at,
                checkpoint.updated_at
            ))
            conn.commit()

    def load_checkpoint(self, job_id: str) -> Optional[JobCheckpoint]:
        """Load existing checkpoint for a job"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT checkpoint_data FROM job_checkpoints WHERE job_id = ?",
                (job_id,)
            )
            row = cursor.fetchone()

            if row:
                data = json.loads(row[0])
                # Reconstruct nested dataclasses
                data['chunks'] = [
                    ChunkCheckpoint(**c) for c in data.get('chunks', [])
                ]
                return JobCheckpoint(**data)
            return None

    def delete_checkpoint(self, job_id: str):
        """Delete checkpoint for a job"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM job_checkpoints WHERE job_id = ?",
                (job_id,)
            )
            conn.commit()

    def get_resumable_jobs(self) -> List[JobCheckpoint]:
        """Find all jobs that can be resumed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT checkpoint_data FROM job_checkpoints
                WHERE json_extract(checkpoint_data, '$.status')
                IN ('transcribing', 'diarizing', 'chunking', 'merging')
            """)

            jobs = []
            for row in cursor.fetchall():
                data = json.loads(row[0])
                data['chunks'] = [
                    ChunkCheckpoint(**c) for c in data.get('chunks', [])
                ]
                jobs.append(JobCheckpoint(**data))
            return jobs

    def create_checkpoint(
        self,
        job_id: str,
        audio_path: str,
        total_chunks: int,
        chunk_duration: int,
        model_size: str,
        language: Optional[str],
        enable_diarization: bool
    ) -> JobCheckpoint:
        """Create a new checkpoint for a job"""
        now = datetime.utcnow().isoformat()

        chunks = [
            ChunkCheckpoint(chunk_index=i, status='pending')
            for i in range(total_chunks)
        ]

        checkpoint = JobCheckpoint(
            job_id=job_id,
            audio_path=audio_path,
            total_chunks=total_chunks,
            chunk_duration=chunk_duration,
            model_size=model_size,
            language=language,
            enable_diarization=enable_diarization,
            created_at=now,
            updated_at=now,
            status='pending',
            current_chunk_index=0,
            chunks=chunks
        )

        self.save_checkpoint(checkpoint)
        return checkpoint

    def update_chunk_info(
        self,
        job_id: str,
        chunk_index: int,
        file_path: str,
        start_time: float,
        end_time: float,
        duration: float
    ):
        """Update chunk file info after chunking"""
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint and chunk_index < len(checkpoint.chunks):
            checkpoint.chunks[chunk_index].file_path = file_path
            checkpoint.chunks[chunk_index].start_time = start_time
            checkpoint.chunks[chunk_index].end_time = end_time
            checkpoint.chunks[chunk_index].duration = duration
            self.save_checkpoint(checkpoint)

    def mark_chunk_started(self, job_id: str, chunk_index: int):
        """Mark a chunk as started processing"""
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint and chunk_index < len(checkpoint.chunks):
            checkpoint.chunks[chunk_index].status = 'processing'
            checkpoint.chunks[chunk_index].started_at = datetime.utcnow().isoformat()
            checkpoint.current_chunk_index = chunk_index
            self.save_checkpoint(checkpoint)

    def mark_chunk_completed(
        self,
        job_id: str,
        chunk_index: int,
        transcript_segments: List[Dict],
        language: str,
        language_probability: float
    ):
        """Mark a chunk as completed with its transcript"""
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint and chunk_index < len(checkpoint.chunks):
            checkpoint.chunks[chunk_index].status = 'completed'
            checkpoint.chunks[chunk_index].completed_at = datetime.utcnow().isoformat()
            checkpoint.chunks[chunk_index].transcript_segments = transcript_segments
            checkpoint.chunks[chunk_index].language = language
            checkpoint.chunks[chunk_index].language_probability = language_probability
            self.save_checkpoint(checkpoint)

    def mark_chunk_failed(
        self,
        job_id: str,
        chunk_index: int,
        error_message: str
    ):
        """Mark a chunk as failed"""
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint and chunk_index < len(checkpoint.chunks):
            checkpoint.chunks[chunk_index].status = 'failed'
            checkpoint.chunks[chunk_index].error_message = error_message
            checkpoint.chunks[chunk_index].retry_count += 1
            self.save_checkpoint(checkpoint)

    def update_job_status(self, job_id: str, status: str):
        """Update the overall job status"""
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint:
            checkpoint.status = status
            self.save_checkpoint(checkpoint)

    def save_diarization(
        self,
        job_id: str,
        segments: List[Dict],
        num_speakers: int
    ):
        """Save diarization results"""
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint:
            checkpoint.diarization_completed = True
            checkpoint.diarization_segments = segments
            checkpoint.num_speakers = num_speakers
            self.save_checkpoint(checkpoint)

    def get_next_pending_chunk(self, job_id: str, max_retries: int = 3) -> Optional[int]:
        """Get the index of the next chunk to process"""
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint:
            for i, chunk in enumerate(checkpoint.chunks):
                if chunk.status == 'pending':
                    return i
                if chunk.status == 'failed' and chunk.retry_count < max_retries:
                    return i
        return None

    def get_completed_chunks_count(self, job_id: str) -> int:
        """Get count of completed chunks"""
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint:
            return sum(1 for c in checkpoint.chunks if c.status == 'completed')
        return 0

    def all_chunks_completed(self, job_id: str) -> bool:
        """Check if all chunks are completed"""
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint:
            return all(c.status == 'completed' for c in checkpoint.chunks)
        return False
