"""
Configuration management for the transcription service (Voxtral Transcribe 2)
"""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    # Paths
    data_dir: str = os.environ.get("DATA_DIR", "./data")
    db_path: str = os.environ.get("DB_PATH", "./data/db/jobs.db")

    # Mistral AI / Voxtral
    mistral_api_key: str = os.environ.get("MISTRAL_API_KEY", "")
    voxtral_model: str = os.environ.get("VOXTRAL_MODEL", "voxtral-mini-latest")

    # Transcription defaults
    enable_diarization: bool = os.environ.get("ENABLE_DIARIZATION", "true").lower() == "true"

    # API timeout in seconds (large files can take a while)
    api_timeout: int = int(os.environ.get("API_TIMEOUT", "3600"))

    # Limits
    max_file_size: int = int(os.environ.get("MAX_FILE_SIZE", str(1024 * 1024 * 1024)))  # 1GB
    max_retry_count: int = int(os.environ.get("MAX_RETRY_COUNT", "3"))

    def __post_init__(self):
        # Ensure directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "uploads"), exist_ok=True)


# Global settings instance
settings = Settings()
