#!/usr/bin/env python3
"""
Service de transcription audio Whisper.cpp pour La Boîte de Chocolat
Version corrigée avec suivi de progression
"""

print("=== VERSION DEBUG 2024-07-18 - WHISPER-CLI ===")

import os
import time
import tempfile
import subprocess
import requests
import logging
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_cors import CORS
from datetime import datetime
import uuid
from flask import send_from_directory
import shutil
import threading
import re
import psutil  # Pour surveiller les ressources système

try:
    from pydub.utils import mediainfo
except ImportError:
    mediainfo = None
import urllib.parse

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["*"])

# Configuration
WHISPER_PATH = "/opt/whisper.cpp"
MODEL_PATH = f"{WHISPER_PATH}/models/ggml-base.bin"
MAX_FILE_SIZE = 150 * 1024 * 1024  # 150MB max

# Dictionnaire global pour stocker l'état des tâches asynchrones
ASYNC_TASKS = {}

# Compteur global pour les transcriptions actives
ACTIVE_TRANSCRIPTIONS = 0
MAX_CONCURRENT_TRANSCRIPTIONS = 1

# Ajout d'un logger global si pas déjà présent
logger = logging.getLogger("__main__")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)


def log_system_resources():
    """Log les ressources système pour debug"""
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        logger.info(f"[SYSTEM] CPU: {cpu_percent}% | RAM: {memory.percent}% ({memory.used // 1024 // 1024}MB/{memory.total // 1024 // 1024}MB)")
    except Exception as e:
        logger.warning(f"[SYSTEM] Impossible de lire les ressources: {e}")


def update_task_progress(task_id, progress, status=None):
    """Fonction utilitaire pour mettre à jour la progression d'une tâche"""
    if task_id and task_id in ASYNC_TASKS:
        old_progress = ASYNC_TASKS[task_id].get("progress", 0)
        old_status = ASYNC_TASKS[task_id].get("status", "")
        
        ASYNC_TASKS[task_id]["progress"] = progress
        if status:
            ASYNC_TASKS[task_id]["status"] = status
        
        # Ne logger que les changements significatifs (tous les 5% ou changement de status)
        if (progress - old_progress >= 5) or (status and status != old_status):
            logger.info(
                f"[ASYNC] Tâche {task_id} : Progression {progress}% - Status: {ASYNC_TASKS[task_id]['status']}"
            )


# Fonction worker pour la transcription asynchrone
def async_transcription_worker(
    task_id,
    audio_url,
    language,
    model,
    output_format="txt",
    word_thold=0.005,
    no_speech_thold=0.40,
    prompt=None,
):
    global ACTIVE_TRANSCRIPTIONS
    try:
        logger.info(
            f"[ASYNC] Tâche {task_id} : Démarrage de la transcription asynchrone"
        )
        update_task_progress(task_id, 5, "processing")

        try:
            logger.info(
                f"[ASYNC] Tâche {task_id} : Appel à run_whisper_transcription..."
            )
            result = run_whisper_transcription(
                audio_url,
                language,
                model,
                output_format,
                word_thold,
                no_speech_thold,
                prompt,
                logger,
                task_id=task_id,
            )
            logger.info(f"[ASYNC] Tâche {task_id} : run_whisper_transcription terminé")

            if result.get("success"):
                # Créer un fichier de transcription comme dans l'endpoint /transcribe/file
                transcription = result.get("transcription", "")
                if transcription:
                    # Créer un nom de fichier basé sur l'URL et le task_id
                    audio_filename = os.path.basename(urllib.parse.urlparse(audio_url).path) or "audio"
                    audio_base = os.path.splitext(audio_filename)[0]
                    transcription_id = task_id
                    output_dir = "/var/log/whisper"
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(
                        output_dir, f"{audio_base}__{transcription_id}.{output_format}"
                    )
                    
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(transcription)
                    
                    # Construire l'URL de téléchargement
                    transcription_url = f"/transcriptions/{audio_base}__{transcription_id}.{output_format}"
                    
                    # Modifier le résultat pour inclure l'URL du fichier
                    result["transcription_url"] = transcription_url
                    result["transcription_file"] = f"{audio_base}__{transcription_id}.{output_format}"
                    # Supprimer la transcription du résultat pour éviter de la retourner directement
                    result.pop("transcription", None)
                
                update_task_progress(task_id, 100, "completed")
                ASYNC_TASKS[task_id]["result"] = result
            else:
                update_task_progress(task_id, 100, "error")
                ASYNC_TASKS[task_id]["result"] = result.get("error", "Erreur inconnue")

        except Exception as e:
            logger.error(
                f"[ASYNC] Tâche {task_id} : Exception dans run_whisper_transcription : {e}"
            )
            update_task_progress(task_id, 100, "error")
            ASYNC_TASKS[task_id]["result"] = str(e)

    except Exception as e:
        logger.error(f"[ASYNC] Tâche {task_id} : Erreur générale : {e}")
        update_task_progress(task_id, 100, "error")
        ASYNC_TASKS[task_id]["result"] = str(e)
    finally:
        logger.info(f"[ASYNC] Tâche {task_id} : Thread terminé")
        ACTIVE_TRANSCRIPTIONS -= 1


# Fonction utilitaire pour nettoyer les fichiers de plus de 24h
def cleanup_old_transcriptions(output_dir="/var/log/whisper", max_age_hours=24):
    now = time.time()
    if not os.path.exists(output_dir):
        return
    for filename in os.listdir(output_dir):
        file_path = os.path.join(output_dir, filename)
        if os.path.isfile(file_path):
            file_age = now - os.path.getmtime(file_path)
            if file_age > max_age_hours * 3600:
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Impossible de supprimer {file_path}: {e}")


# Fonction utilitaire pour construire la commande whisper-cli
def build_whisper_cmd(
    whisper_path,
    model_path,
    temp_file_path,
    language,
    output_format,
    no_timestamps=False,
    word_thold=0.005,
    no_speech_thold=0.40,
    prompt=None,
):
    cmd = [
        f"{whisper_path}/build/bin/whisper-cli",
        "-m",
        model_path,
        "-f",
        temp_file_path,
        "-l",
        language,
        f"-o{output_format}",
        "--word-thold",
        str(word_thold),
        "--no-speech-thold",
        str(no_speech_thold),
    ]
    if prompt:
        cmd.extend(["--prompt", prompt])
    if no_timestamps and output_format == "txt":
        cmd.append("--no-timestamps")
    return cmd


# === FONCTION PRINCIPALE DE TRANSCRIPTION AVEC SUIVI DE PROGRESSION ===
def run_whisper_transcription(
    audio_url,
    language,
    model,
    output_format,
    word_thold,
    no_speech_thold,
    prompt,
    logger,
    request=None,
    task_id=None,
):
    import tempfile, requests, os, subprocess, time, uuid, urllib.parse

    logger.info(f"[WHISPER] Début run_whisper_transcription pour {audio_url}")

    WHISPER_PATH = "/opt/whisper.cpp"
    MODEL_PATH = f"{WHISPER_PATH}/models/ggml-base.bin"
    MAX_FILE_SIZE = 150 * 1024 * 1024
    start_time = time.time()

    # Phase 1: Téléchargement (10-20%)
    update_task_progress(task_id, 10, "downloading")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        response = requests.get(audio_url, stream=True, timeout=90)
        response.raise_for_status()
        file_size = 0
        total_size = int(response.headers.get("content-length", 0))

        for chunk in response.iter_content(chunk_size=8192):
            if file_size > MAX_FILE_SIZE:
                os.unlink(temp_file.name)
                raise Exception("Fichier trop volumineux (max 150MB)")
            temp_file.write(chunk)
            file_size += len(chunk)

            # Mise à jour progression téléchargement
            if total_size > 0 and task_id:
                download_progress = 10 + (file_size / total_size) * 10  # 10-20%
                update_task_progress(task_id, int(download_progress))

        temp_file_path = temp_file.name

    update_task_progress(task_id, 20, "preparing")
    logger.info(f"[WHISPER] Fichier téléchargé: {temp_file_path} ({file_size} bytes)")

    # Phase 2: Préparation du modèle (20-25%)
    model_path = f"{WHISPER_PATH}/models/ggml-{model}.bin"
    if not os.path.exists(model_path):
        model_path = MODEL_PATH

    cmd = build_whisper_cmd(
        WHISPER_PATH,
        model_path,
        temp_file_path,
        language,
        output_format,
        no_timestamps=(output_format == "txt"),
        word_thold=word_thold,
        no_speech_thold=no_speech_thold,
        prompt=prompt,
    )

    update_task_progress(task_id, 25, "transcribing")
    logger.info(f"[WHISPER] Exécution: {' '.join(cmd)}")

    try:
        # Phase 3: Transcription avec suivi de progression (25-95%)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WHISPER_PATH,
            bufsize=1,
            universal_newlines=True,
        )

        # AJOUT MONITORING PID ET DÉBUT
        logger.info(f"[WHISPER] Processus démarré avec PID: {process.pid}")
        logger.info(f"[WHISPER] Début transcription à {datetime.now().isoformat()}")
        
        stdout_lines = []
        stderr_lines = []
        progress_count = 0
        last_progress_update = time.time()
        last_activity_time = time.time()  # Pour détecter les blocages
        last_resource_check = time.time()  # Pour surveiller les ressources

        try:
            while True:
                stdout_line = process.stdout.readline() if process.stdout else None
                stderr_line = process.stderr.readline() if process.stderr else None

                # --- NOUVEAU : Surveillance des ressources système (toutes les 5 min) ---
                current_time = time.time()
                if current_time - last_resource_check > 300:  # 5 minutes
                    log_system_resources()
                    last_resource_check = current_time

                # Vérification de blocage (2 min sans activité)
                if current_time - last_activity_time > 120:
                    logger.warning(f"[WHISPER] Aucune activité depuis 2 minutes, processus peut être bloqué (PID: {process.pid})")
                    last_activity_time = current_time

                # --- NOUVEAU : Timeout global Python (20h) ---
                if current_time - start_time > 72000:
                    logger.error(f"[WHISPER] Timeout global Python dépassé (20h) - PID: {process.pid}")
                    process.kill()
                    update_task_progress(task_id, 100, "error")
                    ASYNC_TASKS[task_id]["result"] = "Timeout global Python dépassé (20h)"
                    break

                # --- NOUVEAU : Surveillance active du process ---
                if process.poll() is not None:
                    logger.info(f"[WHISPER] Processus terminé avec code: {process.returncode} (PID: {process.pid})")
                    if process.returncode != 0:
                        update_task_progress(task_id, 100, "error")
                        ASYNC_TASKS[task_id]["result"] = f"Processus Whisper terminé anormalement (code {process.returncode})"
                    else:
                        update_task_progress(task_id, 90, "finalizing")
                    break

                if stdout_line:
                    last_activity_time = current_time  # Activité détectée
                    stdout_lines.append(stdout_line.strip())
                    line_content = stdout_line.strip()
                    
                    # Log toutes les lignes de stdout pour debug
                    logger.debug(f"[WHISPER] STDOUT: {line_content}")

                    # Analyse de la progression basée sur les logs de Whisper
                    if any(
                        keyword in line_content.lower()
                        for keyword in ["progress", "segment", "frame"]
                    ):
                        progress_count += 1
                        # Estimation de progression basée sur le nombre de segments traités
                        estimated_progress = min(
                            25 + (progress_count * 2), 90
                        )  # 25-90%

                        # Log tous les 100 segments
                        if progress_count % 100 == 0:
                            logger.info(f"[WHISPER] Progression: {progress_count} segments traités (PID: {process.pid})")

                        # Ne pas spammer les mises à jour, max 1 par seconde
                        if time.time() - last_progress_update > 1.0:
                            update_task_progress(task_id, int(estimated_progress))
                            last_progress_update = time.time()

                    # Détecter les pourcentages dans les logs si disponibles
                    percentage_match = re.search(r"(\d+)%", line_content)
                    if percentage_match:
                        whisper_progress = int(percentage_match.group(1))
                        # Mapper le pourcentage de Whisper sur notre échelle 25-90%
                        our_progress = 25 + (whisper_progress * 65 / 100)
                        update_task_progress(task_id, int(our_progress))

                if stderr_line:
                    last_activity_time = current_time  # Activité détectée aussi sur stderr
                    stderr_lines.append(stderr_line.strip())
                    line_content = stderr_line.strip()
                    
                    # Log toutes les lignes de stderr pour debug
                    logger.debug(f"[WHISPER] STDERR: {line_content}")

                    # Logs d'erreur et de progression depuis stderr
                    if "error" in line_content.lower():
                        logger.error(f"[WHISPER] Erreur: {line_content}")
                    elif any(
                        keyword in line_content.lower()
                        for keyword in ["loading", "processing"]
                    ):
                        # Mise à jour progressive pour les étapes de chargement
                        if "loading" in line_content.lower():
                            update_task_progress(task_id, 30)
                        elif "processing" in line_content.lower():
                            update_task_progress(task_id, 35)

            # Phase finale
            update_task_progress(task_id, 90, "finalizing")
            remaining_stdout, remaining_stderr = process.communicate(timeout=86400)
            stdout_lines.extend(remaining_stdout.splitlines())
            stderr_lines.extend(remaining_stderr.splitlines())

        except subprocess.TimeoutExpired:
            logger.error(f"[WHISPER] Timeout du process Whisper (1h) - PID: {process.pid}")
            process.kill()
            raise Exception("Timeout du process Whisper (1h)")

        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)
        result = subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)

    finally:
        os.unlink(temp_file_path)

    if result.returncode != 0:
        logger.error(f"[WHISPER] Erreur Whisper: {result.stderr}")
        raise Exception(f"Erreur transcription: {result.stderr}")

    # Phase 4: Récupération du résultat (95-100%)
    update_task_progress(task_id, 95, "processing_result")

    transcription = None
    base_filename = os.path.basename(temp_file_path)
    ext = f".{output_format}"
    output_filename = base_filename.replace(".mp3", ext)
    output_file = os.path.join(WHISPER_PATH, output_filename)

    logger.info(f"[WHISPER] Recherche du fichier de sortie: {output_file}")

    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            transcription = f.read().strip()
        os.unlink(output_file)
    elif result.stdout and result.stdout.strip():
        transcription = result.stdout.strip()
    else:
        logger.error(f"[WHISPER] Fichier de sortie non trouvé et STDOUT vide")
        raise Exception("Fichier de sortie non trouvé et STDOUT vide")

    processing_time = time.time() - start_time
    logger.info(
        f"[WHISPER] Fin run_whisper_transcription, durée: {processing_time:.2f}s"
    )

    return {
        "success": True,
        "transcription": transcription,
        "model": f"whisper-{model}-{language}",
        "processing_time": processing_time,
        "file_size": file_size,
    }


@app.route("/health", methods=["GET"])
def health():
    """Endpoint de santé pour les health checks"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "model": "whisper-base-fr",
            "version": "1.0.0",
        }
    )


@app.route("/models", methods=["GET"])
def list_models():
    """Lister les modèles disponibles"""
    models_dir = f"{WHISPER_PATH}/models"
    models = []

    if os.path.exists(models_dir):
        for file in os.listdir(models_dir):
            if file.endswith(".bin"):
                models.append(file)

    return jsonify({"models": models, "current_model": os.path.basename(MODEL_PATH)})


# === ENDPOINT SYNCHRONE ===
@app.route("/transcribe", methods=["POST"])
def transcribe():
    global ACTIVE_TRANSCRIPTIONS
    if ACTIVE_TRANSCRIPTIONS >= MAX_CONCURRENT_TRANSCRIPTIONS:
        return (
            jsonify(
                {
                    "error": "Transcription en cours, veuillez réessayer dans quelques minutes"
                }
            ),
            429,
        )
    try:
        ACTIVE_TRANSCRIPTIONS += 1
        data = request.get_json()
        if not data:
            return jsonify({"error": "Données JSON requises"}), 400
        audio_url = data.get("audio_url")
        language = data.get("language", "fr")
        model = data.get("model", "base")
        output_format = data.get("output_format", "txt").lower()
        word_thold = data.get("word_thold", 0.005)
        no_speech_thold = data.get("no_speech_thold", 0.40)
        prompt = data.get("prompt")
        if not audio_url:
            return jsonify({"error": "audio_url requis"}), 400
        result = run_whisper_transcription(
            audio_url,
            language,
            model,
            output_format,
            word_thold,
            no_speech_thold,
            prompt,
            logger,
            request,
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        ACTIVE_TRANSCRIPTIONS -= 1


@app.route("/transcribe-async", methods=["POST"])
def transcribe_async():
    global ACTIVE_TRANSCRIPTIONS

    # Vérifier si une transcription est déjà en cours
    if ACTIVE_TRANSCRIPTIONS >= MAX_CONCURRENT_TRANSCRIPTIONS:
        return (
            jsonify(
                {
                    "error": "Transcription en cours, veuillez réessayer dans quelques minutes"
                }
            ),
            429,
        )

    data = request.get_json()
    if not data:
        return jsonify({"error": "Données JSON requises"}), 400

    audio_url = data.get("audio_url")
    language = data.get("language", "fr")
    model = data.get("model", "base")
    output_format = data.get("output_format", "txt").lower()
    word_thold = data.get("word_thold", 0.005)
    no_speech_thold = data.get("no_speech_thold", 0.40)
    prompt = data.get("prompt")

    if not audio_url:
        return jsonify({"error": "audio_url requis"}), 400

    # Créer une nouvelle tâche
    task_id = str(uuid.uuid4())
    ASYNC_TASKS[task_id] = {
        "status": "pending",
        "result": None,
        "progress": 0,
        "created_at": datetime.now().isoformat(),
    }

    ACTIVE_TRANSCRIPTIONS += 1

    # Lancer le thread de transcription
    thread = threading.Thread(
        target=async_transcription_worker,
        args=(
            task_id,
            audio_url,
            language,
            model,
            output_format,
            word_thold,
            no_speech_thold,
            prompt,
        ),
    )
    thread.daemon = True  # Thread daemon pour éviter les blocages
    thread.start()

    return jsonify(
        {
            "task_id": task_id,
            "status_url": f"/transcription-status/{task_id}",
            "status": "pending",
        }
    )


@app.route("/reset-transcriptions", methods=["POST"])
def reset_transcriptions():
    """Réinitialiser le compteur de transcriptions actives (debug)"""
    global ACTIVE_TRANSCRIPTIONS, ASYNC_TASKS
    
    # Nettoyer les tâches fantômes (plus de 2h)
    current_time = time.time()
    tasks_to_remove = []
    
    for task_id, task in ASYNC_TASKS.items():
        if task.get("status") == "processing":
            created_time = datetime.fromisoformat(task.get("created_at", "2020-01-01T00:00:00"))
            if (current_time - created_time.timestamp()) > 86400:  # 24h
                tasks_to_remove.append(task_id)
    
    for task_id in tasks_to_remove:
        del ASYNC_TASKS[task_id]
        logger.info(f"[RESET] Tâche fantôme supprimée: {task_id}")
    
    # Réinitialiser le compteur
    old_count = ACTIVE_TRANSCRIPTIONS
    ACTIVE_TRANSCRIPTIONS = 0
    
    logger.info(f"[RESET] Transcriptions actives: {old_count} → 0")
    
    return jsonify({
        "success": True,
        "message": f"Compteur réinitialisé: {old_count} → 0",
        "tasks_removed": len(tasks_to_remove),
        "active_transcriptions": ACTIVE_TRANSCRIPTIONS
    })


@app.route("/transcription-status/<task_id>", methods=["GET"])
def transcription_status(task_id):
    task = ASYNC_TASKS.get(task_id)
    if not task:
        return jsonify({"error": "Tâche inconnue"}), 404

    response = {
        "task_id": task_id,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "created_at": task.get("created_at"),
    }

    # Inclure le résultat seulement si la tâche est terminée
    if task["status"] in ["completed", "error"]:
        response["result"] = task["result"]

    return jsonify(response)


# === AUTRES ENDPOINTS ===
@app.route("/transcribe/file", methods=["POST"])
def transcribe_file():
    global ACTIVE_TRANSCRIPTIONS
    start_time = time.time()

    if ACTIVE_TRANSCRIPTIONS >= MAX_CONCURRENT_TRANSCRIPTIONS:
        return (
            jsonify(
                {
                    "error": "Transcription en cours, veuillez réessayer dans quelques minutes"
                }
            ),
            429,
        )

    try:
        ACTIVE_TRANSCRIPTIONS += 1
        if "audio_file" not in request.files:
            return jsonify({"error": "Aucun fichier audio fourni"}), 400

        audio_file = request.files["audio_file"]
        if audio_file.filename == "":
            return jsonify({"error": "Aucun fichier sélectionné"}), 400

        language = request.form.get("language", "fr")
        model = request.form.get("model", "base")
        output_format = request.form.get("output_format", "txt").lower()

        logger.info(f"Début transcription fichier: {audio_file.filename}")

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            audio_file.save(temp_file.name)
            temp_file_path = temp_file.name
            file_size = os.path.getsize(temp_file_path)

        logger.info(f"Fichier sauvegardé: {temp_file_path} ({file_size} bytes)")

        model_path = f"{WHISPER_PATH}/models/ggml-{model}.bin"
        if not os.path.exists(model_path):
            model_path = MODEL_PATH

        cmd = build_whisper_cmd(
            WHISPER_PATH,
            model_path,
            temp_file_path,
            language,
            output_format,
            no_timestamps=(output_format == "txt"),
            word_thold=float(request.form.get("word_thold", 0.005)),
            no_speech_thold=float(request.form.get("no_speech_thold", 0.40)),
            prompt=request.form.get("prompt"),
        )

        logger.info(f"Exécution: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WHISPER_PATH,
            bufsize=1,
            universal_newlines=True,
        )

        try:
            stdout_lines = []
            stderr_lines = []

            while True:
                stdout_line = process.stdout.readline() if process.stdout else None
                stderr_line = process.stderr.readline() if process.stderr else None

                if stdout_line:
                    stdout_lines.append(stdout_line.strip())
                if stderr_line:
                    stderr_lines.append(stderr_line.strip())
                if process.poll() is not None:
                    break

            remaining_stdout, remaining_stderr = process.communicate()
            stdout_lines.extend(remaining_stdout.splitlines())
            stderr_lines.extend(remaining_stderr.splitlines())

            stdout = "\n".join(stdout_lines)
            stderr = "\n".join(stderr_lines)
            result = subprocess.CompletedProcess(
                cmd, process.returncode, stdout, stderr
            )

        except subprocess.TimeoutExpired:
            process.kill()
            raise

        os.unlink(temp_file_path)

        if result.returncode != 0:
            logger.error(f"Erreur Whisper: {result.stderr}")
            return jsonify({"error": f"Erreur transcription: {result.stderr}"}), 500

        transcription = None
        if result.stdout and result.stdout.strip() and output_format == "txt":
            transcription = result.stdout.strip()
        else:
            base_filename = os.path.basename(temp_file_path)
            ext = f".{output_format}"
            output_filename = base_filename.replace(".mp3", ext)
            output_file = os.path.join(WHISPER_PATH, output_filename)

            if os.path.exists(output_file):
                with open(output_file, "r", encoding="utf-8") as f:
                    transcription = f.read().strip()
                os.unlink(output_file)
            else:
                return (
                    jsonify({"error": "Fichier de sortie non trouvé et STDOUT vide"}),
                    500,
                )

        processing_time = time.time() - start_time
        cleanup_old_transcriptions()

        if len(transcription) > 2000:
            audio_filename = audio_file.filename or "audio"
            audio_base = os.path.splitext(secure_filename(audio_filename))[0]
            transcription_id = str(uuid.uuid4())
            output_dir = "/var/log/whisper"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(
                output_dir, f"{audio_base}__{transcription_id}.{output_format}"
            )
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(transcription)
            transcription_url = (
                request.url_root.rstrip("/")
                + f"/transcriptions/{audio_base}__{transcription_id}.{output_format}"
            )
            return jsonify(
                {
                    "success": True,
                    "transcription_url": transcription_url,
                    "model": f"whisper-{model}-{language}",
                    "processing_time": processing_time,
                    "file_size": file_size,
                    "filename": audio_file.filename,
                }
            )
        else:
            return jsonify(
                {
                    "success": True,
                    "transcription": transcription,
                    "model": f"whisper-{model}-{language}",
                    "processing_time": processing_time,
                    "file_size": file_size,
                    "filename": audio_file.filename,
                }
            )

    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        ACTIVE_TRANSCRIPTIONS -= 1


@app.route("/transcriptions/<path:transcription_file>", methods=["GET"])
def get_transcription_file(transcription_file):
    output_dir = "/var/log/whisper"
    return send_from_directory(output_dir, transcription_file, as_attachment=True)


@app.route("/transcriptions-list", methods=["GET"])
def list_transcriptions():
    output_dir = "/var/log/whisper"
    base_url = request.url_root.rstrip("/") + "/transcriptions/"
    if not os.path.exists(output_dir):
        return jsonify([])
    files = [
        f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))
    ]
    result = [{"filename": f, "url": base_url + f} for f in files]
    return jsonify(result)


if __name__ == "__main__":
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Modèle non trouvé: {MODEL_PATH}")
        exit(1)

    logger.info(f"Service Whisper démarré avec le modèle: {MODEL_PATH}")
    
    # Configuration production
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
