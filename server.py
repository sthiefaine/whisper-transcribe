#!/usr/bin/env python3
"""
Whisper Transcription Service - Optimized for Large Files
Handles 200MB+ files with resource constraints: 8GB RAM, 2.5 CPU max
"""

import os
import time
import uuid
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor

import requests
import psutil
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Configuration
WHISPER_PATH = "/opt/whisper.cpp" if os.path.exists("/opt/whisper.cpp") else os.path.expanduser("~/whisper.cpp")
OUTPUT_DIR = Path("/var/log/whisper")
WORK_DIR = OUTPUT_DIR / "work"
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
MAX_CONCURRENT = 1  # Only one transcription at a time for large files
CHUNK_SIZE = 8192
TIMEOUT_HOURS = 4

# Create directories
OUTPUT_DIR.mkdir(exist_ok=True)
WORK_DIR.mkdir(exist_ok=True)

@dataclass
class TranscriptionTask:
    id: str
    audio_url: str
    model: str
    language: str
    output_format: str
    word_thold: float
    no_speech_thold: float
    prompt: Optional[str]
    created_at: datetime
    status: str = "pending"
    progress: int = 0
    file_size: int = 0
    result_file: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self):
        return {
            **asdict(self),
            'created_at': self.created_at.isoformat(),
            'elapsed_time': f"{(datetime.now() - self.created_at).total_seconds() / 3600:.1f}h"
        }

class ResourceMonitor:
    """Monitor CPU and memory usage"""
    
    @staticmethod
    def get_usage():
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used_mb': memory.used // 1024 // 1024,
            'memory_total_mb': memory.total // 1024 // 1024
        }
    
    @staticmethod
    def check_limits():
        """Check if we're within resource limits - relaxed for Docker containers"""
        usage = ResourceMonitor.get_usage()
        # Only check CPU, let Docker handle memory limits
        if usage['cpu_percent'] > 300:  # Allow some headroom
            return False, f"CPU usage too high: {usage['cpu_percent']}%"
        # Remove strict memory check - Docker handles this via cgroups
        return True, None

class FileDownloader:
    """Efficient file downloader with progress tracking"""
    
    @staticmethod
    def download(url: str, filepath: Path, task: TranscriptionTask, progress_callback=None) -> bool:
        try:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if downloaded > MAX_FILE_SIZE:
                        filepath.unlink(missing_ok=True)
                        raise Exception(f"File too large (max {MAX_FILE_SIZE//1024//1024}MB)")
                    
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size > 0:
                        progress = min(15, int((downloaded / total_size) * 15))  # 0-15%
                        progress_callback(progress)
            
            task.file_size = downloaded
            return True
            
        except Exception as e:
            task.error = f"Download failed: {str(e)}"
            return False

class WhisperTranscriber:
    """Optimized Whisper transcription with progress tracking"""
    
    def __init__(self):
        self.whisper_path = WHISPER_PATH
        
    def get_model_path(self, model: str) -> str:
        model_file = f"ggml-{model}.bin"
        model_path = Path(self.whisper_path) / "models" / model_file
        if model_path.exists():
            return str(model_path)
        # Fallback to base model
        return str(Path(self.whisper_path) / "models" / "ggml-base.bin")
    
    def build_command(self, audio_file: Path, model: str, language: str, 
                     output_format: str, word_thold: float, no_speech_thold: float,
                     prompt: Optional[str] = None) -> list:
        model_path = self.get_model_path(model)
        
        cmd = [
            str(Path(self.whisper_path) / "build" / "bin" / "whisper-cli"),
            "-m", model_path,
            "-f", str(audio_file),
            "-l", language,
            f"-o{output_format}",
            "--word-thold", str(word_thold),
            "--no-speech-thold", str(no_speech_thold),
            "--threads", "2",  # Limit to 2 threads max
            "--verbose",  # Force verbose output for monitoring
            "--print-colors",  # Ensure output is printed
            "--print-progress",  # Force progress output
            "--print-special", "false",  # Reduce noise
            "--print-realtime", "false"  # Avoid real-time issues
        ]
        
        if prompt:
            cmd.extend(["--prompt", prompt])
        if output_format == "txt":
            cmd.append("--no-timestamps")
            
        return cmd
    
    def transcribe(self, task: TranscriptionTask, audio_file: Path, 
                  progress_callback=None) -> Optional[str]:
        cmd = self.build_command(
            audio_file, task.model, task.language, task.output_format,
            task.word_thold, task.no_speech_thold, task.prompt
        )
        
        try:
            # Enhanced process creation with better monitoring
            import os
            env = os.environ.copy()
            env['OMP_NUM_THREADS'] = '2'  # Limit OpenMP threads
            env['MKL_NUM_THREADS'] = '2'  # Limit MKL threads
            env['CUDA_VISIBLE_DEVICES'] = ''  # Force CPU only for stability
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.whisper_path,
                env=env,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Create process group
            )
            
            # Monitor process with timeout
            start_time = time.time()
            timeout = TIMEOUT_HOURS * 3600
            
            last_activity = time.time()
            last_output_time = time.time()
            output_lines = []
            error_lines = []
            
            # Real-time monitoring with output capture
            while process.poll() is None:
                current_time = time.time()
                elapsed = current_time - start_time
                
                if elapsed > timeout:
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    except:
                        process.terminate()
                    time.sleep(5)
                    if process.poll() is None:
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        except:
                            process.kill()
                    raise Exception(f"Transcription timeout ({TIMEOUT_HOURS}h)")
                
                # Read output non-blocking
                import select
                ready, _, _ = select.select([process.stdout, process.stderr], [], [], 1)
                
                got_output = False
                for stream in ready:
                    line = stream.readline()
                    if line:
                        got_output = True
                        last_output_time = current_time
                        if stream == process.stdout:
                            output_lines.append(line.strip())
                            # Parse progress from whisper output
                            if any(word in line.lower() for word in ['progress', '%', 'segment']):
                                # Extract percentage if present
                                import re
                                match = re.search(r'(\d+)%', line)
                                if match:
                                    whisper_progress = int(match.group(1))
                                    progress = 20 + int(whisper_progress * 0.7)  # 20-90%
                                    if progress_callback:
                                        progress_callback(progress)
                        else:
                            error_lines.append(line.strip())
                
                # Check if process is alive and working
                try:
                    proc_info = psutil.Process(process.pid)
                    if not proc_info.is_running():
                        raise Exception("Whisper process died unexpectedly")
                    
                    # If no output for too long, it might be stuck
                    if current_time - last_output_time > 1800:  # 30 minutes no output
                        # Send SIGCONT to try to wake it up
                        try:
                            os.kill(process.pid, signal.SIGCONT)
                            print(f"Sent SIGCONT to potentially stuck process {process.pid}")
                            last_output_time = current_time  # Reset timer
                        except:
                            pass
                        
                        # If still no output after trying to wake up, consider it stuck
                        if current_time - last_activity > 3600:  # 1 hour total silence
                            raise Exception("Process stuck - no output for 1 hour")
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    raise Exception("Whisper process died unexpectedly")
                
                # Update progress based on time if no output progress
                if not got_output and progress_callback:
                    estimated_duration = task.file_size / (1024 * 1024) * 2  # 2min per MB
                    progress = min(90, int(20 + (elapsed / estimated_duration) * 70))
                    progress_callback(progress)
                
                time.sleep(2)  # Check every 2 seconds for better responsiveness
            
            # Collect any remaining output
            remaining_stdout, remaining_stderr = process.communicate()
            if remaining_stdout:
                output_lines.extend(remaining_stdout.splitlines())
            if remaining_stderr:
                error_lines.extend(remaining_stderr.splitlines())
            
            stdout = '\n'.join(output_lines)
            stderr = '\n'.join(error_lines)
            
            if process.returncode != 0:
                error_msg = f"Whisper failed (code {process.returncode}): {stderr}"
                if "out of memory" in stderr.lower():
                    error_msg = "Out of memory - file too large for available RAM"
                elif "cuda" in stderr.lower():
                    error_msg = "CUDA error - using CPU fallback"
                raise Exception(error_msg)
            
            # Find output file
            base_name = audio_file.stem
            output_file = Path(self.whisper_path) / f"{base_name}.{task.output_format}"
            
            if output_file.exists():
                content = output_file.read_text(encoding='utf-8')
                output_file.unlink()  # Clean up
                return content
            elif stdout.strip():
                return stdout.strip()
            else:
                # Last resort: check for any .srt/.txt files created recently
                for ext in [task.output_format, 'txt', 'srt']:
                    pattern = f"*.{ext}"
                    recent_files = sorted(
                        Path(self.whisper_path).glob(pattern),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True
                    )
                    if recent_files:
                        newest = recent_files[0]
                        if time.time() - newest.stat().st_mtime < 300:  # Created in last 5 min
                            content = newest.read_text(encoding='utf-8')
                            newest.unlink()
                            return content
                
                raise Exception("No transcription output found")
                
        except Exception as e:
            task.error = str(e)
            return None

class TranscriptionService:
    """Main service for handling transcription tasks"""
    
    def __init__(self):
        self.tasks: Dict[str, TranscriptionTask] = {}
        self.executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT)
        self.transcriber = WhisperTranscriber()
        self.is_processing = False
        
    def create_task(self, audio_url: str, model: str, language: str,
                   output_format: str, word_thold: float, no_speech_thold: float,
                   prompt: Optional[str] = None) -> str:
        
        if self.is_processing:
            raise Exception("Another transcription is already in progress")
            
        task_id = str(uuid.uuid4())
        task = TranscriptionTask(
            id=task_id,
            audio_url=audio_url,
            model=model,
            language=language,
            output_format=output_format,
            word_thold=word_thold,
            no_speech_thold=no_speech_thold,
            prompt=prompt,
            created_at=datetime.now()
        )
        
        self.tasks[task_id] = task
        self.executor.submit(self._process_task, task)
        
        return task_id
    
    def _process_task(self, task: TranscriptionTask):
        self.is_processing = True
        
        try:
            # Update progress callback
            def update_progress(progress: int, status: str = None):
                task.progress = progress
                if status:
                    task.status = status
            
            update_progress(0, "downloading")
            
            # Download file
            audio_file = WORK_DIR / f"audio_{task.id}.mp3"
            downloader = FileDownloader()
            
            if not downloader.download(task.audio_url, audio_file, task, 
                                     lambda p: update_progress(p, "downloading")):
                return
            
            update_progress(20, "transcribing")
            
            # Transcribe
            result = self.transcriber.transcribe(
                task, audio_file, 
                lambda p: update_progress(p, "transcribing")
            )
            
            if result:
                # Save result
                result_filename = f"{Path(task.audio_url).stem}_{task.id}.{task.output_format}"
                result_path = OUTPUT_DIR / result_filename
                result_path.write_text(result, encoding='utf-8')
                
                task.result_file = result_filename
                task.status = "completed"
                task.progress = 100
            else:
                task.status = "error"
                task.progress = 100
                
        except Exception as e:
            task.error = str(e)
            task.status = "error"
            task.progress = 100
            
        finally:
            # Clean up
            audio_file.unlink(missing_ok=True)
            self.is_processing = False
    
    def get_task(self, task_id: str) -> Optional[TranscriptionTask]:
        return self.tasks.get(task_id)
    
    def list_tasks(self) -> list:
        return [task.to_dict() for task in self.tasks.values()]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old tasks and files"""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        
        to_remove = []
        for task_id, task in self.tasks.items():
            if task.created_at.timestamp() < cutoff:
                # Remove result file if exists
                if task.result_file:
                    result_path = OUTPUT_DIR / task.result_file
                    result_path.unlink(missing_ok=True)
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.tasks[task_id]

# Initialize service
app = Flask(__name__)
CORS(app, origins=["*"])
service = TranscriptionService()

@app.route("/health", methods=["GET"])
def health():
    usage = ResourceMonitor.get_usage()
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "is_processing": service.is_processing,
        "resource_usage": usage
    })

@app.route("/transcribe-async", methods=["POST"])
def transcribe_async():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON data required"}), 400
        
        # Validate required fields
        audio_url = data.get("audio_url")
        if not audio_url:
            return jsonify({"error": "audio_url required"}), 400
        
        # Quick availability check
        if service.is_processing:
            return jsonify({"error": "Another transcription is already in progress"}), 429
        
        task_id = service.create_task(
            audio_url=audio_url,
            model=data.get("model", "large-v3"),
            language=data.get("language", "fr"),
            output_format=data.get("output_format", "srt"),
            word_thold=data.get("word_thold", 0.005),
            no_speech_thold=data.get("no_speech_thold", 0.40),
            prompt=data.get("prompt")
        )
        
        return jsonify({
            "task_id": task_id,
            "status_url": f"/status/{task_id}",
            "status": "pending"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/status/<task_id>", methods=["GET"])
def get_status(task_id: str):
    task = service.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    response = task.to_dict()
    
    # Add download URL if completed
    if task.status == "completed" and task.result_file:
        response["download_url"] = f"/download/{task.result_file}"
    
    return jsonify(response)

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return jsonify({"error": "File not found"}), 404
    
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

@app.route("/list", methods=["GET"])
def list_transcriptions():
    """List all available transcription files with metadata"""
    files = []
    
    for file_path in OUTPUT_DIR.glob("*.*"):
        if file_path.is_file() and file_path.suffix in ['.srt', '.txt', '.vtt']:
            stat = file_path.stat()
            files.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "download_url": f"/download/{file_path.name}"
            })
    
    # Sort by creation time, newest first
    files.sort(key=lambda x: x["created_at"], reverse=True)
    
    return jsonify({
        "files": files,
        "total": len(files),
        "current_tasks": service.list_tasks()
    })

@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify({
        "tasks": service.list_tasks(),
        "is_processing": service.is_processing
    })

@app.route("/reset", methods=["POST"])
def reset_service():
    """Force reset the service if stuck"""
    service.is_processing = False
    # Kill any running processes
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'whisper' in proc.info['name'].lower():
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return jsonify({
        "success": True,
        "message": "Service reset, processing flag cleared"
    })

def cleanup_handler(signum, _):
    """Graceful shutdown"""
    print(f"Received signal {signum}, shutting down gracefully...")
    service.cleanup_old_tasks()
    exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGTERM, cleanup_handler)
    signal.signal(signal.SIGINT, cleanup_handler)
    
    # Cleanup old files on startup
    service.cleanup_old_tasks()
    
    print("🚀 Whisper Transcription Service")
    print(f"📁 Whisper path: {WHISPER_PATH}")
    print(f"📂 Output directory: {OUTPUT_DIR}")
    print(f"⏱️ Timeout: {TIMEOUT_HOURS}h")
    print(f"💾 Max file size: {MAX_FILE_SIZE//1024//1024}MB")
    print(f"🔄 Max concurrent: {MAX_CONCURRENT}")
    
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
        threaded=True
    )