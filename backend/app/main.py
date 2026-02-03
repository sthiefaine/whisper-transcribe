"""
Main FastAPI application
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional, List
import os
import uuid
import asyncio
import shutil
from datetime import datetime
import logging

from .config import settings
from .database import Database
from .services.checkpoint import CheckpointManager
from .services.job_processor import JobProcessor, ProcessingProgress
from .services.audio_chunker import AudioChunker
from .api.websocket import WebSocketManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="Podcast Transcription API",
    description="Robust chunk-based transcription with checkpoint support",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
db = Database(settings.db_path)
checkpoint_manager = CheckpointManager(settings.checkpoint_db_path)
ws_manager = WebSocketManager()

# Active processors
active_processors: dict[str, JobProcessor] = {}


# === LIFECYCLE ===

@app.on_event("startup")
async def startup_event():
    """Startup: check for resumable jobs"""
    logger.info("Starting Podcast Transcription API")
    logger.info(f"Data directory: {settings.data_dir}")
    logger.info(f"Model: {settings.model_size}")
    logger.info(f"Device: {settings.device}")

    # List resumable jobs (don't auto-resume, let user decide)
    resumable = checkpoint_manager.get_resumable_jobs()
    if resumable:
        logger.info(f"Found {len(resumable)} resumable jobs:")
        for job in resumable:
            logger.info(f"  - {job.job_id} (status: {job.status})")


# === UPLOAD ENDPOINTS ===

@app.post("/api/jobs", tags=["Jobs"])
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    model_size: str = Form("large-v3"),
    enable_diarization: bool = Form(True),
    num_speakers: Optional[int] = Form(None)
):
    """
    Upload an audio file and create a transcription job.
    The job will be processed in the background with checkpoint support.
    """
    # Generate job ID
    job_id = str(uuid.uuid4())

    # Save uploaded file
    upload_dir = os.path.join(settings.data_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    file_ext = os.path.splitext(file.filename or ".mp3")[1] or ".mp3"
    file_path = os.path.join(upload_dir, f"{job_id}{file_ext}")

    # Stream file to disk to handle large files
    file_size = 0
    with open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            f.write(chunk)
            file_size += len(chunk)

    logger.info(f"Uploaded file: {file.filename} ({file_size} bytes) -> {file_path}")

    # Get audio duration
    duration = None
    try:
        chunker = AudioChunker()
        info = chunker.get_audio_info(file_path)
        duration = info.duration
    except Exception as e:
        logger.warning(f"Could not get audio duration: {e}")

    # Create job record
    job = db.create_job(
        job_id=job_id,
        filename=file.filename or "unknown.mp3",
        original_path=file_path,
        file_size=file_size,
        duration_seconds=duration,
        model_size=model_size,
        language=language,
        enable_diarization=enable_diarization,
        num_speakers=num_speakers
    )

    # Start background processing
    background_tasks.add_task(
        process_job_background,
        job_id=job_id,
        audio_path=file_path,
        language=language,
        model_size=model_size,
        enable_diarization=enable_diarization,
        num_speakers=num_speakers
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "filename": file.filename,
        "file_size": file_size,
        "duration_seconds": duration,
        "message": "Job created and queued for processing"
    }


async def process_job_background(
    job_id: str,
    audio_path: str,
    language: Optional[str],
    model_size: str,
    enable_diarization: bool,
    num_speakers: Optional[int]
):
    """Background task to process a job"""

    def progress_callback(progress: ProcessingProgress):
        # Update database
        db.update_job_status(
            job_id=progress.job_id,
            status='processing' if progress.status != 'completed' else 'completed',
            current_chunk=progress.current_chunk,
            completed_chunks=progress.current_chunk if progress.current_phase != 'chunking' else 0
        )
        # Broadcast via WebSocket
        asyncio.create_task(ws_manager.broadcast_progress(progress))

    processor = JobProcessor(
        data_dir=settings.data_dir,
        checkpoint_manager=checkpoint_manager,
        model_size=model_size,
        chunk_duration=settings.chunk_duration,
        device=settings.device,
        compute_type=settings.compute_type,
        cpu_threads=settings.cpu_threads,
        hf_token=settings.hf_token,
        progress_callback=progress_callback
    )

    active_processors[job_id] = processor

    try:
        result = await processor.process_job(
            job_id=job_id,
            audio_path=audio_path,
            language=language,
            enable_diarization=enable_diarization,
            num_speakers=num_speakers
        )

        # Save transcript to database
        if result.get('transcript'):
            transcript = result['transcript']
            db.save_transcript(
                job_id=job_id,
                full_text=transcript.get('text', ''),
                segments=transcript.get('segments', []),
                language=transcript.get('language', 'unknown'),
                language_probability=transcript.get('language_probability', 0),
                num_speakers=transcript.get('num_speakers'),
                diarization=transcript.get('diarization')
            )

        db.update_job_status(job_id, 'completed')
        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        db.update_job_status(job_id, 'failed', error_message=str(e))
    finally:
        active_processors.pop(job_id, None)


# === JOB MANAGEMENT ENDPOINTS ===

@app.get("/api/jobs", tags=["Jobs"])
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List all jobs with optional status filter"""
    jobs = db.list_jobs(status=status, limit=limit, offset=offset)
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/jobs/{job_id}", tags=["Jobs"])
async def get_job(job_id: str):
    """Get job details by ID"""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/api/jobs/{job_id}", tags=["Jobs"])
async def delete_job(job_id: str):
    """Delete a job and its data"""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Stop processing if active
    if job_id in active_processors:
        active_processors[job_id].stop()

    # Delete files
    if job.get('original_path') and os.path.exists(job['original_path']):
        os.remove(job['original_path'])

    # Delete chunks
    chunks_dir = os.path.join(settings.data_dir, 'chunks', job_id)
    if os.path.exists(chunks_dir):
        shutil.rmtree(chunks_dir)

    # Delete checkpoint
    checkpoint_manager.delete_checkpoint(job_id)

    # Delete from database
    db.delete_job(job_id)

    return {"message": "Job deleted"}


@app.post("/api/jobs/{job_id}/resume", tags=["Jobs"])
async def resume_job(job_id: str, background_tasks: BackgroundTasks):
    """Resume a failed or interrupted job"""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job['status'] not in ('failed', 'processing', 'transcribing', 'diarizing', 'chunking'):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume job with status '{job['status']}'"
        )

    # Check for checkpoint
    checkpoint = checkpoint_manager.load_checkpoint(job_id)
    if not checkpoint:
        raise HTTPException(
            status_code=400,
            detail="No checkpoint found for this job"
        )

    # Check if already running
    if job_id in active_processors:
        raise HTTPException(
            status_code=400,
            detail="Job is already running"
        )

    # Resume processing
    background_tasks.add_task(
        process_job_background,
        job_id=job_id,
        audio_path=job['original_path'],
        language=job.get('language'),
        model_size=job['model_size'],
        enable_diarization=job['enable_diarization'],
        num_speakers=job.get('num_speakers')
    )

    return {"message": "Job resumed", "job_id": job_id}


@app.post("/api/jobs/{job_id}/cancel", tags=["Jobs"])
async def cancel_job(job_id: str):
    """Cancel a running job"""
    if job_id in active_processors:
        active_processors[job_id].stop()
        db.update_job_status(job_id, 'cancelled')
        return {"message": "Job cancelled"}

    raise HTTPException(status_code=400, detail="Job is not currently running")


# === TRANSCRIPT ENDPOINTS ===

@app.get("/api/jobs/{job_id}/transcript", tags=["Transcripts"])
async def get_transcript(job_id: str):
    """Get the transcript for a completed job"""
    transcript = db.get_transcript(job_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript


@app.get("/api/jobs/{job_id}/transcript/download", tags=["Transcripts"])
async def download_transcript(
    job_id: str,
    format: str = "txt"  # txt, srt, vtt, json
):
    """Download transcript in various formats"""
    transcript = db.get_transcript(job_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    job = db.get_job(job_id)
    base_filename = os.path.splitext(job['filename'])[0]

    if format == "txt":
        content = transcript['full_text']
        media_type = "text/plain"
        filename = f"{base_filename}.txt"

    elif format == "srt":
        content = generate_srt(transcript['segments'])
        media_type = "text/srt"
        filename = f"{base_filename}.srt"

    elif format == "vtt":
        content = generate_vtt(transcript['segments'])
        media_type = "text/vtt"
        filename = f"{base_filename}.vtt"

    elif format == "json":
        import json
        content = json.dumps(transcript, indent=2)
        media_type = "application/json"
        filename = f"{base_filename}.json"

    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {format}")

    return StreamingResponse(
        iter([content.encode()]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def generate_srt(segments: List[dict]) -> str:
    """Generate SRT subtitle format"""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_timestamp_srt(seg['start'])
        end = format_timestamp_srt(seg['end'])
        speaker = seg.get('speaker', '')
        text = f"[{speaker}] {seg['text']}" if speaker else seg['text']
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def generate_vtt(segments: List[dict]) -> str:
    """Generate WebVTT subtitle format"""
    lines = ["WEBVTT\n"]
    for seg in segments:
        start = format_timestamp_vtt(seg['start'])
        end = format_timestamp_vtt(seg['end'])
        speaker = seg.get('speaker', '')
        text = f"<v {speaker}>{seg['text']}" if speaker else seg['text']
        lines.append(f"\n{start} --> {end}\n{text}")
    return "\n".join(lines)


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds as VTT timestamp (HH:MM:SS.mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


# === HEALTH ENDPOINTS ===

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/api/system/status", tags=["System"])
async def system_status():
    """Get system status including active jobs"""
    resumable = checkpoint_manager.get_resumable_jobs()
    return {
        "active_jobs": len(active_processors),
        "active_job_ids": list(active_processors.keys()),
        "resumable_jobs": len(resumable),
        "resumable_job_ids": [j.job_id for j in resumable],
        "config": {
            "model_size": settings.model_size,
            "device": settings.device,
            "chunk_duration": settings.chunk_duration,
            "diarization_enabled": bool(settings.hf_token)
        }
    }


@app.get("/api/models", tags=["System"])
async def list_models():
    """List available models"""
    return {
        "models": [
            {"id": "tiny", "name": "Tiny", "description": "Fastest, lowest quality"},
            {"id": "base", "name": "Base", "description": "Fast, low quality"},
            {"id": "small", "name": "Small", "description": "Balanced speed/quality"},
            {"id": "medium", "name": "Medium", "description": "Good quality"},
            {"id": "large-v1", "name": "Large V1", "description": "High quality"},
            {"id": "large-v2", "name": "Large V2", "description": "Higher quality"},
            {"id": "large-v3", "name": "Large V3", "description": "Best quality (default)"},
        ],
        "default": settings.model_size
    }


# === WEBSOCKET ENDPOINT ===

@app.websocket("/ws/progress/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time progress updates"""
    await ws_manager.connect(websocket, job_id)
    try:
        while True:
            # Keep connection alive, receive pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, job_id)
