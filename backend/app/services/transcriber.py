"""
Transcriber Service - Voxtral Transcribe 2 via Mistral AI API
"""
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    segments: List[Dict[str, Any]]
    language: str
    num_speakers: Optional[int]
    usage: Optional[Dict[str, Any]]


class VoxtralTranscriber:
    def __init__(
        self,
        api_key: str,
        model: str = "voxtral-mini-latest",
        timeout: int = 3600,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        if self._client is None:
            from mistralai import Mistral
            self._client = Mistral(api_key=self.api_key)
        return self._client

    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        enable_diarization: bool = True,
    ) -> TranscriptionResult:
        """Send full audio file to Voxtral Transcribe 2 API."""
        client = self._get_client()

        file_name = Path(audio_path).name

        logger.info(f"Sending {file_name} to Voxtral API (model={self.model}, diarize={enable_diarization})")

        with open(audio_path, "rb") as f:
            # Note: timestamp_granularities and language cannot be used together
            # So we use timestamp_granularities for segment timing when no language specified
            response = await client.audio.transcriptions.complete_async(
                model=self.model,
                file={"content": f, "file_name": file_name},
                diarize=enable_diarization,
                timestamp_granularities=["segment"] if not language else None,
                language=language,
                timeout_ms=self.timeout * 1000,
            )

        # Parse segments
        segments: List[Dict[str, Any]] = []
        speakers_seen: set[str] = set()

        if response.segments:
            for seg in response.segments:
                segment_dict: Dict[str, Any] = {
                    "text": seg.text.strip(),
                    "start": seg.start,
                    "end": seg.end,
                }
                if enable_diarization and seg.speaker_id:
                    segment_dict["speaker"] = seg.speaker_id
                    speakers_seen.add(seg.speaker_id)
                segments.append(segment_dict)

        usage_dict = None
        if response.usage:
            usage_dict = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
                "completion_tokens": getattr(response.usage, "completion_tokens", None),
                "total_tokens": getattr(response.usage, "total_tokens", None),
            }

        logger.info(
            f"Transcription complete: {len(segments)} segments, "
            f"{len(speakers_seen)} speakers, lang={response.language}"
        )

        return TranscriptionResult(
            text=response.text,
            segments=segments,
            language=response.language or language or "unknown",
            num_speakers=len(speakers_seen) if speakers_seen else None,
            usage=usage_dict,
        )

    @staticmethod
    def _get_mime_type(path: str) -> str:
        mime_map = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".flac": "audio/flac",
            ".ogg": "audio/ogg",
        }
        return mime_map.get(Path(path).suffix.lower(), "audio/mpeg")
