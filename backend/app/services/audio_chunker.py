"""
Audio Chunker Service
Splits audio files into processable chunks using FFmpeg
"""
import subprocess
import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AudioChunk:
    index: int
    start_time: float  # seconds
    end_time: float    # seconds
    file_path: str
    duration: float


@dataclass
class AudioInfo:
    duration: float
    sample_rate: int
    channels: int
    format: str


class AudioChunker:
    def __init__(
        self,
        chunk_duration: int = 300,  # 5 minutes default
        overlap: int = 2,            # 2 seconds overlap for context
        output_format: str = "wav",
        sample_rate: int = 16000     # Whisper optimal sample rate
    ):
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.output_format = output_format
        self.sample_rate = sample_rate

    def get_audio_info(self, audio_path: str) -> AudioInfo:
        """Get audio file metadata using ffprobe"""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        audio_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
            {}
        )

        return AudioInfo(
            duration=float(data["format"]["duration"]),
            sample_rate=int(audio_stream.get("sample_rate", 44100)),
            channels=int(audio_stream.get("channels", 2)),
            format=data["format"]["format_name"]
        )

    def split_audio(
        self,
        audio_path: str,
        output_dir: str,
        job_id: str
    ) -> List[AudioChunk]:
        """Split audio file into chunks"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        info = self.get_audio_info(audio_path)
        chunks: List[AudioChunk] = []

        current_time = 0.0
        index = 0

        while current_time < info.duration:
            # Calculate chunk boundaries
            # Add overlap from previous chunk (except for first chunk)
            start_time = max(0, current_time - self.overlap) if index > 0 else 0
            end_time = min(current_time + self.chunk_duration, info.duration)
            duration = end_time - start_time

            # Output file path
            chunk_path = os.path.join(
                output_dir,
                f"{job_id}_chunk_{index:04d}.{self.output_format}"
            )

            # Extract chunk using ffmpeg
            cmd = [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(start_time),
                "-t", str(duration),
                "-ar", str(self.sample_rate),
                "-ac", "1",  # Mono for Whisper
                "-acodec", "pcm_s16le" if self.output_format == "wav" else "libmp3lame",
                chunk_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)

            chunks.append(AudioChunk(
                index=index,
                start_time=start_time,
                end_time=end_time,
                file_path=chunk_path,
                duration=duration
            ))

            current_time += self.chunk_duration
            index += 1

        return chunks

    def cleanup_chunks(self, output_dir: str, job_id: str):
        """Remove chunk files for a job"""
        import shutil
        job_chunks_dir = os.path.join(output_dir, job_id)
        if os.path.exists(job_chunks_dir):
            shutil.rmtree(job_chunks_dir)
