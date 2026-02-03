"""
Job Processor
Main orchestration service for transcription jobs
"""
import os
import asyncio
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, asdict
import logging

from .audio_chunker import AudioChunker
from .transcriber import Transcriber
from .diarizer import Diarizer, DiarizationResult, SpeakerSegment
from .checkpoint import CheckpointManager, JobCheckpoint

logger = logging.getLogger(__name__)


@dataclass
class ProcessingProgress:
    job_id: str
    status: str
    current_chunk: int
    total_chunks: int
    percent_complete: float
    current_phase: str  # 'chunking', 'transcribing', 'diarizing', 'merging'
    estimated_remaining_seconds: Optional[int] = None
    message: Optional[str] = None


class JobProcessor:
    def __init__(
        self,
        data_dir: str,
        checkpoint_manager: CheckpointManager,
        model_size: str = "large-v3",
        chunk_duration: int = 300,
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        hf_token: Optional[str] = None,
        progress_callback: Optional[Callable[[ProcessingProgress], None]] = None
    ):
        self.data_dir = data_dir
        self.checkpoint_manager = checkpoint_manager
        self.model_size = model_size
        self.chunk_duration = chunk_duration
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.hf_token = hf_token
        self.progress_callback = progress_callback

        # Initialize services
        self.chunker = AudioChunker(chunk_duration=chunk_duration)
        self.transcriber: Optional[Transcriber] = None
        self.diarizer: Optional[Diarizer] = None

        # Processing state
        self._is_running = False
        self._should_stop = False

    def _report_progress(self, progress: ProcessingProgress):
        """Send progress update via callback"""
        if self.progress_callback:
            try:
                self.progress_callback(progress)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    async def process_job(
        self,
        job_id: str,
        audio_path: str,
        language: Optional[str] = None,
        enable_diarization: bool = True,
        num_speakers: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process a transcription job with checkpoint support"""

        self._is_running = True
        self._should_stop = False

        try:
            # Check for existing checkpoint (resume support)
            checkpoint = self.checkpoint_manager.load_checkpoint(job_id)

            if checkpoint is None:
                # New job - create checkpoint
                checkpoint = await self._initialize_job(
                    job_id, audio_path, language, enable_diarization
                )
            else:
                logger.info(f"Resuming job {job_id} from checkpoint (status: {checkpoint.status})")

            # Phase 1: Chunking (if not done)
            if checkpoint.status == 'pending':
                await self._phase_chunking(checkpoint, audio_path)
                checkpoint = self.checkpoint_manager.load_checkpoint(job_id)

            # Phase 2: Transcription
            if checkpoint.status in ('chunking', 'transcribing'):
                await self._phase_transcription(checkpoint, language)
                checkpoint = self.checkpoint_manager.load_checkpoint(job_id)

            # Phase 3: Diarization (if enabled)
            if enable_diarization and checkpoint.status == 'diarizing':
                await self._phase_diarization(checkpoint, audio_path, num_speakers)
                checkpoint = self.checkpoint_manager.load_checkpoint(job_id)

            # Phase 4: Merge results
            if checkpoint.status in ('transcribing', 'diarizing', 'merging'):
                await self._phase_merge(checkpoint, enable_diarization)
                checkpoint = self.checkpoint_manager.load_checkpoint(job_id)

            return {
                'job_id': job_id,
                'status': 'completed',
                'transcript': checkpoint.merged_transcript
            }

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            self.checkpoint_manager.update_job_status(job_id, 'failed')
            raise
        finally:
            self._is_running = False
            # Cleanup: unload models to free memory
            if self.transcriber:
                self.transcriber.unload_model()
            if self.diarizer:
                self.diarizer.unload_pipeline()

    async def _initialize_job(
        self,
        job_id: str,
        audio_path: str,
        language: Optional[str],
        enable_diarization: bool
    ) -> JobCheckpoint:
        """Initialize a new job with chunking info"""

        logger.info(f"Initializing new job: {job_id}")

        # Get audio duration to calculate chunks
        info = self.chunker.get_audio_info(audio_path)
        num_chunks = int(info.duration / self.chunk_duration) + 1

        logger.info(f"Audio duration: {info.duration:.1f}s, chunks: {num_chunks}")

        # Create checkpoint
        checkpoint = self.checkpoint_manager.create_checkpoint(
            job_id=job_id,
            audio_path=audio_path,
            total_chunks=num_chunks,
            chunk_duration=self.chunk_duration,
            model_size=self.model_size,
            language=language,
            enable_diarization=enable_diarization
        )

        return checkpoint

    async def _phase_chunking(self, checkpoint: JobCheckpoint, audio_path: str):
        """Split audio into chunks"""

        logger.info(f"Phase: Chunking job {checkpoint.job_id}")

        self._report_progress(ProcessingProgress(
            job_id=checkpoint.job_id,
            status='processing',
            current_chunk=0,
            total_chunks=checkpoint.total_chunks,
            percent_complete=0,
            current_phase='chunking',
            message='Splitting audio into chunks...'
        ))

        chunks_dir = os.path.join(self.data_dir, 'chunks', checkpoint.job_id)
        chunks = self.chunker.split_audio(
            audio_path,
            chunks_dir,
            checkpoint.job_id
        )

        # Update checkpoint with chunk file paths
        for chunk in chunks:
            self.checkpoint_manager.update_chunk_info(
                checkpoint.job_id,
                chunk.index,
                chunk.file_path,
                chunk.start_time,
                chunk.end_time,
                chunk.duration
            )

        self.checkpoint_manager.update_job_status(checkpoint.job_id, 'transcribing')
        logger.info(f"Chunking complete: {len(chunks)} chunks created")

    async def _phase_transcription(
        self,
        checkpoint: JobCheckpoint,
        language: Optional[str]
    ):
        """Transcribe all chunks"""

        logger.info(f"Phase: Transcription job {checkpoint.job_id}")

        # Load transcriber model once for all chunks
        if self.transcriber is None:
            self.transcriber = Transcriber(
                model_size=self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads
            )
        self.transcriber.load_model()

        self.checkpoint_manager.update_job_status(checkpoint.job_id, 'transcribing')

        # Process each chunk
        while True:
            if self._should_stop:
                logger.info(f"Job {checkpoint.job_id} stop requested")
                break

            # Reload checkpoint to get latest state
            checkpoint = self.checkpoint_manager.load_checkpoint(checkpoint.job_id)

            # Get next chunk to process
            chunk_idx = self.checkpoint_manager.get_next_pending_chunk(checkpoint.job_id)
            if chunk_idx is None:
                break  # All chunks done

            chunk = checkpoint.chunks[chunk_idx]
            completed_count = self.checkpoint_manager.get_completed_chunks_count(checkpoint.job_id)

            self._report_progress(ProcessingProgress(
                job_id=checkpoint.job_id,
                status='processing',
                current_chunk=chunk_idx + 1,
                total_chunks=checkpoint.total_chunks,
                percent_complete=(completed_count / checkpoint.total_chunks) * 80,  # 80% for transcription
                current_phase='transcribing',
                message=f'Transcribing chunk {chunk_idx + 1}/{checkpoint.total_chunks}'
            ))

            try:
                # Mark chunk as started
                self.checkpoint_manager.mark_chunk_started(checkpoint.job_id, chunk_idx)

                # Transcribe chunk
                result = self.transcriber.transcribe_chunk(
                    audio_path=chunk.file_path,
                    chunk_index=chunk_idx,
                    original_start_time=chunk.start_time,
                    language=language
                )

                # Adjust timestamps and convert to dict
                adjusted_segments = [
                    {
                        'start': seg.start + chunk.start_time,
                        'end': seg.end + chunk.start_time,
                        'text': seg.text,
                        'words': seg.words
                    }
                    for seg in result.segments
                ]

                self.checkpoint_manager.mark_chunk_completed(
                    checkpoint.job_id,
                    chunk_idx,
                    adjusted_segments,
                    result.language,
                    result.language_probability
                )

                logger.info(f"Chunk {chunk_idx + 1}/{checkpoint.total_chunks} completed")

                # Small delay to prevent CPU overload
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Chunk {chunk_idx} failed: {e}")
                self.checkpoint_manager.mark_chunk_failed(
                    checkpoint.job_id,
                    chunk_idx,
                    str(e)
                )
                # Continue to next chunk, will retry failed ones later

        # Check if all chunks completed
        if self.checkpoint_manager.all_chunks_completed(checkpoint.job_id):
            if checkpoint.enable_diarization:
                self.checkpoint_manager.update_job_status(checkpoint.job_id, 'diarizing')
            else:
                self.checkpoint_manager.update_job_status(checkpoint.job_id, 'merging')

            # Unload transcriber to free memory for diarization
            self.transcriber.unload_model()

    async def _phase_diarization(
        self,
        checkpoint: JobCheckpoint,
        audio_path: str,
        num_speakers: Optional[int]
    ):
        """Run speaker diarization"""

        logger.info(f"Phase: Diarization job {checkpoint.job_id}")

        self._report_progress(ProcessingProgress(
            job_id=checkpoint.job_id,
            status='processing',
            current_chunk=checkpoint.total_chunks,
            total_chunks=checkpoint.total_chunks,
            percent_complete=85,
            current_phase='diarizing',
            message='Identifying speakers...'
        ))

        # Load diarizer
        if self.diarizer is None:
            self.diarizer = Diarizer(
                hf_token=self.hf_token,
                device=self.device
            )

        try:
            self.diarizer.load_pipeline()

            # Run diarization on original file
            result = self.diarizer.diarize(
                audio_path,
                num_speakers=num_speakers
            )

            # Store diarization result
            self.checkpoint_manager.save_diarization(
                checkpoint.job_id,
                self.diarizer.to_dict_list(result),
                result.num_speakers
            )

            self.checkpoint_manager.update_job_status(checkpoint.job_id, 'merging')
            logger.info(f"Diarization complete: {result.num_speakers} speakers found")

        finally:
            # Unload diarizer to free memory
            self.diarizer.unload_pipeline()

    async def _phase_merge(self, checkpoint: JobCheckpoint, enable_diarization: bool):
        """Merge all chunk transcripts and align with speakers"""

        logger.info(f"Phase: Merging job {checkpoint.job_id}")

        self._report_progress(ProcessingProgress(
            job_id=checkpoint.job_id,
            status='processing',
            current_chunk=checkpoint.total_chunks,
            total_chunks=checkpoint.total_chunks,
            percent_complete=95,
            current_phase='merging',
            message='Merging transcripts...'
        ))

        # Reload checkpoint to get all data
        checkpoint = self.checkpoint_manager.load_checkpoint(checkpoint.job_id)

        # Collect all segments from chunks
        all_segments: List[Dict] = []
        detected_language = 'unknown'
        language_probability = 0.0

        for chunk in sorted(checkpoint.chunks, key=lambda c: c.chunk_index):
            if chunk.transcript_segments:
                all_segments.extend(chunk.transcript_segments)
                if chunk.language:
                    detected_language = chunk.language
                    language_probability = chunk.language_probability or 0.0

        # Remove duplicates from overlapping regions
        all_segments = self._deduplicate_segments(all_segments)

        # Align with speakers if diarization was done
        num_speakers = None
        diarization_segments = None

        if enable_diarization and checkpoint.diarization_completed and checkpoint.diarization_segments:
            # Reconstruct DiarizationResult
            diarization = DiarizationResult(
                segments=[
                    SpeakerSegment(**s) for s in checkpoint.diarization_segments
                ],
                num_speakers=checkpoint.num_speakers or 0
            )

            if self.diarizer is None:
                self.diarizer = Diarizer(hf_token=self.hf_token)

            all_segments = self.diarizer.align_transcript_with_speakers(
                all_segments, diarization
            )
            num_speakers = diarization.num_speakers
            diarization_segments = checkpoint.diarization_segments

        # Build final transcript
        full_text = ' '.join(seg['text'] for seg in all_segments)

        merged_transcript = {
            'segments': all_segments,
            'text': full_text,
            'language': detected_language,
            'language_probability': language_probability,
            'num_speakers': num_speakers,
            'diarization': diarization_segments
        }

        # Update checkpoint with merged result
        cp = self.checkpoint_manager.load_checkpoint(checkpoint.job_id)
        cp.merged_transcript = merged_transcript
        cp.status = 'completed'
        self.checkpoint_manager.save_checkpoint(cp)

        self._report_progress(ProcessingProgress(
            job_id=checkpoint.job_id,
            status='completed',
            current_chunk=checkpoint.total_chunks,
            total_chunks=checkpoint.total_chunks,
            percent_complete=100,
            current_phase='completed',
            message='Transcription complete!'
        ))

        logger.info(f"Job {checkpoint.job_id} completed: {len(all_segments)} segments, {len(full_text.split())} words")

    def _deduplicate_segments(self, segments: List[Dict]) -> List[Dict]:
        """Remove duplicate segments from overlapping chunk boundaries"""
        if not segments:
            return []

        # Sort by start time
        segments = sorted(segments, key=lambda s: s['start'])

        deduplicated = [segments[0]]

        for seg in segments[1:]:
            last = deduplicated[-1]

            # Check for significant overlap (within 0.5 seconds)
            if seg['start'] < last['end'] - 0.5:
                # Segments overlap - keep the one with more content
                if len(seg['text']) > len(last['text']):
                    deduplicated[-1] = seg
            else:
                deduplicated.append(seg)

        return deduplicated

    def stop(self):
        """Signal the processor to stop after current chunk"""
        self._should_stop = True
        logger.info("Stop requested")

    @property
    def is_running(self) -> bool:
        """Check if processor is currently running"""
        return self._is_running
