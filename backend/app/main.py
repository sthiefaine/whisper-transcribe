"""
Main FastAPI application - Voxtral Transcribe 2
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional, List
import os
import uuid
import asyncio
import subprocess
from datetime import datetime
import logging

from .config import settings
from .database import Database
from .services.job_processor import JobProcessor, ProcessingProgress
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
    description="Audio transcription powered by Voxtral Transcribe 2",
    version="2.0.0"
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
ws_manager = WebSocketManager()

# Active processors
active_processors: dict[str, JobProcessor] = {}


def get_audio_duration(file_path: str) -> Optional[float]:
    """Get audio duration via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-show_entries",
                "format=duration", "-of", "csv=p=0", file_path
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not get audio duration: {e}")
    return None


# === LIFECYCLE ===

@app.on_event("startup")
async def startup_event():
    """Startup: validate configuration"""
    logger.info("Starting Podcast Transcription API (Voxtral)")
    logger.info(f"Voxtral model: {settings.voxtral_model}")
    logger.info(f"Diarization enabled: {settings.enable_diarization}")

    if not settings.mistral_api_key:
        logger.error("MISTRAL_API_KEY not set! Transcription will fail.")


# === UPLOAD ENDPOINTS ===

@app.post("/api/jobs", tags=["Jobs"])
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    enable_diarization: bool = Form(True),
    num_speakers: Optional[int] = Form(None)
):
    """
    Upload an audio file and create a transcription job.
    The job will be processed in the background via Voxtral API.
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

    # Get audio duration via ffprobe
    duration = get_audio_duration(file_path)

    # Create job record
    job = db.create_job(
        job_id=job_id,
        filename=file.filename or "unknown.mp3",
        original_path=file_path,
        file_size=file_size,
        duration_seconds=duration,
        model_size=settings.voxtral_model,
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
    enable_diarization: bool,
    num_speakers: Optional[int]
):
    """Background task to process a job"""

    def progress_callback(progress: ProcessingProgress):
        # Update database
        db.update_job_status(
            job_id=progress.job_id,
            status='processing' if progress.status != 'completed' else 'completed',
        )
        # Broadcast via WebSocket
        asyncio.create_task(ws_manager.broadcast_progress(progress))

    processor = JobProcessor(
        api_key=settings.mistral_api_key,
        model=settings.voxtral_model,
        api_timeout=settings.api_timeout,
        progress_callback=progress_callback,
    )

    active_processors[job_id] = processor

    try:
        result = await processor.process_job(
            job_id=job_id,
            audio_path=audio_path,
            language=language,
            enable_diarization=enable_diarization,
            num_speakers=num_speakers,
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

    # Delete uploaded file
    if job.get('original_path') and os.path.exists(job['original_path']):
        os.remove(job['original_path'])

    # Delete from database
    db.delete_job(job_id)

    return {"message": "Job deleted"}


@app.post("/api/jobs/{job_id}/retry", tags=["Jobs"])
async def retry_job(job_id: str, background_tasks: BackgroundTasks):
    """Retry a failed job"""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job['status'] != 'failed':
        raise HTTPException(
            status_code=400,
            detail="Only failed jobs can be retried"
        )

    # Check if already running
    if job_id in active_processors:
        raise HTTPException(
            status_code=400,
            detail="Job is already running"
        )

    # Retry processing
    background_tasks.add_task(
        process_job_background,
        job_id=job_id,
        audio_path=job['original_path'],
        language=job.get('language'),
        enable_diarization=job['enable_diarization'],
        num_speakers=job.get('num_speakers')
    )

    return {"message": "Job retried", "job_id": job_id}


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
        "version": "2.0.0"
    }


@app.get("/api/system/status", tags=["System"])
async def system_status():
    """Get system status including active jobs"""
    return {
        "active_jobs": len(active_processors),
        "active_job_ids": list(active_processors.keys()),
        "config": {
            "voxtral_model": settings.voxtral_model,
            "diarization_enabled": settings.enable_diarization,
            "api_configured": bool(settings.mistral_api_key),
        }
    }


@app.get("/api/models", tags=["System"])
async def list_models():
    """List available models"""
    return {
        "models": [
            {"id": "voxtral-mini-latest", "name": "Voxtral Mini", "description": "Transcription rapide via Mistral AI"},
        ],
        "default": settings.voxtral_model
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
