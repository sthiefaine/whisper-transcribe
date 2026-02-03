"""
Transcriber Service
Wrapper around faster-whisper with memory-efficient processing
"""
import os
import gc
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: Optional[List[Dict]] = None
    confidence: Optional[float] = None


@dataclass
class ChunkTranscript:
    chunk_index: int
    original_start_time: float
    segments: List[TranscriptSegment]
    language: str
    language_probability: float


class Transcriber:
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: Optional[str] = None,
        cpu_threads: int = 4
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.download_root = download_root or os.path.expanduser(
            "~/.cache/huggingface/hub"
        )
        self.cpu_threads = cpu_threads
        self._model = None

    def load_model(self):
        """Load model into memory (singleton pattern for reuse)"""
        if self._model is not None:
            return

        from faster_whisper import WhisperModel

        logger.info(f"Loading Whisper model: {self.model_size}")
        logger.info(f"Device: {self.device}, Compute type: {self.compute_type}")

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=self.download_root,
            cpu_threads=self.cpu_threads,
            num_workers=1  # Single worker to limit memory
        )

        logger.info("Model loaded successfully")

    def unload_model(self):
        """Unload model to free memory"""
        if self._model is not None:
            del self._model
            self._model = None
            gc.collect()

            # Try to clear CUDA cache if available
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

            logger.info("Model unloaded")

    def transcribe_chunk(
        self,
        audio_path: str,
        chunk_index: int,
        original_start_time: float,
        language: Optional[str] = None,
        task: str = "transcribe",
        word_timestamps: bool = True,
        vad_filter: bool = True
    ) -> ChunkTranscript:
        """Transcribe a single audio chunk"""

        if self._model is None:
            self.load_model()

        logger.info(f"Transcribing chunk {chunk_index}: {audio_path}")

        # Transcribe with VAD filter to skip silence
        segments_gen, info = self._model.transcribe(
            audio_path,
            language=language,
            task=task,
            word_timestamps=word_timestamps,
            vad_filter=vad_filter,
            vad_parameters={
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 200
            },
            beam_size=5,
            best_of=5,
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            condition_on_previous_text=True
        )

        # Convert generator to list of segments
        transcript_segments: List[TranscriptSegment] = []
        for segment in segments_gen:
            words = None
            if word_timestamps and hasattr(segment, 'words') and segment.words:
                words = [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "probability": w.probability
                    }
                    for w in segment.words
                ]

            transcript_segments.append(TranscriptSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text.strip(),
                words=words,
                confidence=getattr(segment, 'avg_logprob', None)
            ))

        logger.info(f"Chunk {chunk_index}: {len(transcript_segments)} segments transcribed")

        return ChunkTranscript(
            chunk_index=chunk_index,
            original_start_time=original_start_time,
            segments=transcript_segments,
            language=info.language,
            language_probability=info.language_probability
        )

    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self._model is not None
