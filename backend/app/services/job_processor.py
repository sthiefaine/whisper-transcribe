"""
Job Processor - Simplified pipeline using Voxtral Transcribe 2
"""
import asyncio
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
import logging

from .transcriber import VoxtralTranscriber

logger = logging.getLogger(__name__)


@dataclass
class ProcessingProgress:
    job_id: str
    status: str  # 'processing', 'completed', 'failed'
    percent_complete: float
    current_phase: str  # 'transcribing', 'completed'
    message: Optional[str] = None
    total_eta_seconds: Optional[int] = None


class JobProcessor:
    def __init__(
        self,
        api_key: str,
        model: str = "voxtral-mini-latest",
        api_timeout: int = 3600,
        progress_callback: Optional[Callable[[ProcessingProgress], None]] = None,
    ):
        self.transcriber = VoxtralTranscriber(
            api_key=api_key,
            model=model,
            timeout=api_timeout,
        )
        self.progress_callback = progress_callback
        self._is_running = False
        self._should_stop = False

    def _report_progress(self, progress: ProcessingProgress):
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
        num_speakers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process a transcription job via Voxtral API."""
        self._is_running = True
        self._should_stop = False

        try:
            # Report start
            self._report_progress(ProcessingProgress(
                job_id=job_id,
                status='processing',
                percent_complete=10,
                current_phase='transcribing',
                message='Envoi au service Voxtral...',
            ))

            # Start heartbeat task to show progress while API call is in flight
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(job_id)
            )

            try:
                result = await self.transcriber.transcribe(
                    audio_path=audio_path,
                    language=language,
                    enable_diarization=enable_diarization,
                )
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

            # Build transcript dict
            transcript = {
                'text': result.text,
                'segments': result.segments,
                'language': result.language,
                'language_probability': 1.0,
                'num_speakers': result.num_speakers,
                'diarization': None,
            }

            self._report_progress(ProcessingProgress(
                job_id=job_id,
                status='completed',
                percent_complete=100,
                current_phase='completed',
                message='Transcription terminee !',
            ))

            return {
                'job_id': job_id,
                'status': 'completed',
                'transcript': transcript,
            }

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            self._report_progress(ProcessingProgress(
                job_id=job_id,
                status='failed',
                percent_complete=0,
                current_phase='transcribing',
                message=f'Erreur: {str(e)}',
            ))
            raise
        finally:
            self._is_running = False

    async def _heartbeat_loop(self, job_id: str):
        """Send periodic progress updates while API call is in flight."""
        percent = 15
        while True:
            await asyncio.sleep(30)
            if percent < 90:
                percent += 5
            self._report_progress(ProcessingProgress(
                job_id=job_id,
                status='processing',
                percent_complete=percent,
                current_phase='transcribing',
                message='Transcription en cours...',
            ))

    def stop(self):
        self._should_stop = True
        logger.info("Stop requested")

    @property
    def is_running(self) -> bool:
        return self._is_running
