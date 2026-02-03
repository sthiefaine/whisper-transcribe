"""
Diarizer Service
Speaker diarization using pyannote-audio
Runs as a separate pass to manage memory
"""
import os
import gc
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    speaker: str
    start: float
    end: float


@dataclass
class DiarizationResult:
    segments: List[SpeakerSegment]
    num_speakers: int


class Diarizer:
    def __init__(
        self,
        hf_token: Optional[str] = None,
        device: str = "cpu"
    ):
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self.device = device
        self._pipeline = None

    def load_pipeline(self):
        """Load pyannote diarization pipeline"""
        if self._pipeline is not None:
            return

        if not self.hf_token:
            raise ValueError(
                "HuggingFace token required for speaker diarization. "
                "Set HF_TOKEN environment variable or pass hf_token parameter."
            )

        from pyannote.audio import Pipeline
        import torch

        logger.info("Loading pyannote speaker diarization pipeline...")

        # Use pyannote/speaker-diarization-3.1
        self._pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=self.hf_token
        )

        # Move to appropriate device
        if self.device == "cuda" and torch.cuda.is_available():
            self._pipeline.to(torch.device("cuda"))

        logger.info("Diarization pipeline loaded")

    def unload_pipeline(self):
        """Unload pipeline to free memory"""
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
            gc.collect()

            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

            logger.info("Diarization pipeline unloaded")

    def diarize(
        self,
        audio_path: str,
        num_speakers: Optional[int] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> DiarizationResult:
        """Run speaker diarization on audio file"""

        if self._pipeline is None:
            self.load_pipeline()

        logger.info(f"Running diarization on: {audio_path}")

        # Configure speaker count hints
        kwargs = {}
        if num_speakers is not None:
            kwargs["num_speakers"] = num_speakers
        elif min_speakers is not None or max_speakers is not None:
            kwargs["min_speakers"] = min_speakers or 1
            kwargs["max_speakers"] = max_speakers or 10

        # Run diarization
        diarization = self._pipeline(audio_path, **kwargs)

        # Extract speaker segments
        segments: List[SpeakerSegment] = []
        speakers_seen = set()

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(SpeakerSegment(
                speaker=speaker,
                start=turn.start,
                end=turn.end
            ))
            speakers_seen.add(speaker)

        logger.info(f"Diarization complete: {len(segments)} segments, {len(speakers_seen)} speakers")

        return DiarizationResult(
            segments=segments,
            num_speakers=len(speakers_seen)
        )

    def align_transcript_with_speakers(
        self,
        transcript_segments: List[Dict],
        diarization: DiarizationResult
    ) -> List[Dict]:
        """
        Align transcript segments with speaker labels
        Uses temporal intersection approach
        """
        aligned_segments = []

        for seg in transcript_segments:
            seg_start = seg['start']
            seg_end = seg['end']

            # Find overlapping speaker segments
            speaker_overlaps: Dict[str, float] = {}

            for spk_seg in diarization.segments:
                # Calculate intersection
                overlap_start = max(seg_start, spk_seg.start)
                overlap_end = min(seg_end, spk_seg.end)
                overlap_duration = max(0, overlap_end - overlap_start)

                if overlap_duration > 0:
                    speaker_overlaps[spk_seg.speaker] = (
                        speaker_overlaps.get(spk_seg.speaker, 0) + overlap_duration
                    )

            # Assign speaker with most overlap
            if speaker_overlaps:
                speaker = max(speaker_overlaps, key=speaker_overlaps.get)
            else:
                speaker = "UNKNOWN"

            aligned_segments.append({
                **seg,
                'speaker': speaker
            })

        return aligned_segments

    def is_loaded(self) -> bool:
        """Check if pipeline is loaded"""
        return self._pipeline is not None

    def to_dict_list(self, result: DiarizationResult) -> List[Dict]:
        """Convert diarization result segments to dict list"""
        return [asdict(seg) for seg in result.segments]
