"""
Configuration management for the transcription service
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    # Paths
    data_dir: str = os.environ.get("DATA_DIR", "./data")
    db_path: str = os.environ.get("DB_PATH", "./data/db/jobs.db")
    checkpoint_db_path: str = os.environ.get("CHECKPOINT_DB_PATH", "./data/db/checkpoints.db")
    model_cache_dir: str = os.environ.get("MODEL_CACHE_DIR", os.path.expanduser("~/.cache/huggingface/hub"))

    # Processing
    chunk_duration: int = int(os.environ.get("CHUNK_DURATION", "300"))  # 5 minutes
    chunk_overlap: int = int(os.environ.get("CHUNK_OVERLAP", "2"))  # 2 seconds
    model_size: str = os.environ.get("MODEL_SIZE", "large-v3")
    device: str = os.environ.get("DEVICE", "cpu")
    compute_type: str = os.environ.get("COMPUTE_TYPE", "int8")
    cpu_threads: int = int(os.environ.get("CPU_THREADS", "4"))

    # Diarization
    hf_token: Optional[str] = os.environ.get("HF_TOKEN")

    # Limits
    max_file_size: int = int(os.environ.get("MAX_FILE_SIZE", str(500 * 1024 * 1024)))  # 500MB
    max_retry_count: int = int(os.environ.get("MAX_RETRY_COUNT", "3"))

    def __post_init__(self):
        # Ensure directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "chunks"), exist_ok=True)


# Global settings instance
settings = Settings()
