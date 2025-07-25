#!/usr/bin/env python3
"""
Service de transcription audio Whisper.cpp pour La Boîte de Chocolat
Version corrigée pour transcriptions longue durée (20h+)
"""

print("=== VERSION DEBUG 2024-07-25 - WHISPER-CLI LONGUE DUREE ===")

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

# Désactiver les logs verbeux de Werkzeug/Flask
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('flask').setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app, origins=["*"])

# Configuration
# Détection automatique du mode (Docker vs Local)
if os.path.exists("/opt/whisper.cpp"):
    # Mode Docker
    WHISPER_PATH = "/opt/whisper.cpp"
    print("🐳 Mode Docker détecté")
else:
    # Mode Local macOS
    WHISPER_PATH = os.path.expanduser("~/whisper.cpp")
    print("💻 Mode Local macOS détecté")

MODEL_PATH = f"{WHISPER_PATH}/models/ggml-base.bin"
MAX_FILE_SIZE = 150 * 1024 * 1024  # 150MB max

# Dictionnaire global pour stocker l'état des tâches asynchrones
ASYNC_TASKS = {}

# Compteur global pour les transcriptions actives
ACTIVE_TRANSCRIPTIONS = 0
MAX_CONCURRENT_TRANSCRIPTIONS = 1

# Configuration pour éviter les kills par Coolify
import signal
import atexit

def signal_handler(signum, frame):
    """Gestionnaire de signal pour arrêt gracieux"""
    logger.warning(f"[SYSTEM] Signal {signum} reçu, arrêt gracieux en cours...")
    # Sauvegarder l'état des tâches en cours
    for task_id, task in ASYNC_TASKS.items():
        if task.get("status") == "processing":
            logger.info(f"[SYSTEM] Sauvegarde de la tâche {task_id} avant arrêt")
    sys.exit(0)

# Enregistrer les gestionnaires de signal
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def cleanup_on_exit():
    """Nettoyage à la sortie"""
    logger.info("[SYSTEM] Nettoyage à la sortie...")
    for task_id, task in ASYNC_TASKS.items():
        if task.get("status") == "processing":
            logger.warning(f"[SYSTEM] Tâche {task_id} encore en cours à la sortie")

atexit.register(cleanup_on_exit)

# NOUVEAUX TIMEOUTS POUR LONGUE DUREE - VERSION ULTRA ROBUSTE
MAX_TRANSCRIPTION_TIME = 86400  # 24h au lieu de 20h pour plus de marge
ACTIVITY_TIMEOUT = 7200  # 2h au lieu de 1h pour éviter faux positifs
RESOURCE_CHECK_INTERVAL = 180  # 3 min pour surveillance plus fréquente
PROCESS_HEARTBEAT_INTERVAL = 180  # 3 min pour heartbeat du processus
COOLIFY_KEEPALIVE_INTERVAL = 60  # 1 min pour keepalive Coolify

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
        
        # Ne logger que les changements significatifs (tous les 10% ou changement de status)
        if (progress - old_progress >= 10) or (status and status != old_status):
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


# === FONCTION PRINCIPALE DE TRANSCRIPTION AVEC SUIVI DE PROGRESSION LONGUE DUREE ===
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

    # Détection automatique du mode (Docker vs Local)
    if os.path.exists("/opt/whisper.cpp"):
        WHISPER_PATH = "/opt/whisper.cpp"  # Mode Docker
    else:
        WHISPER_PATH = os.path.expanduser("~/whisper.cpp")  # Mode Local macOS
    
    MODEL_PATH = f"{WHISPER_PATH}/models/ggml-base.bin"
    MAX_FILE_SIZE = 150 * 1024 * 1024
    start_time = time.time()

    # Phase 1: Téléchargement (10-20%)
    update_task_progress(task_id, 10, "downloading")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        response = requests.get(audio_url, stream=True, timeout=300)  # Augmenté à 5min
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
        # Phase 3: Transcription avec suivi de progression LONGUE DUREE (25-95%)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WHISPER_PATH,
            bufsize=1,
            universal_newlines=True,
        )

        # MONITORING PID ET DÉBUT
        logger.info(f"[WHISPER] Processus démarré avec PID: {process.pid}")
        logger.info(f"[WHISPER] Début transcription à {datetime.now().isoformat()}")
        logger.info(f"[WHISPER] Timeout configuré pour: {MAX_TRANSCRIPTION_TIME/3600:.1f}h")
        
        stdout_lines = []
        stderr_lines = []
        progress_count = 0
        last_progress_update = time.time()
        last_activity_time = time.time()
        last_resource_check = time.time()
        last_major_log = time.time()  # Pour logger moins souvent

        try:
            while True:
                stdout_line = process.stdout.readline() if process.stdout else None
                stderr_line = process.stderr.readline() if process.stderr else None

                current_time = time.time()
                
                # --- Surveillance des ressources système (toutes les 10 min) ---
                if current_time - last_resource_check > RESOURCE_CHECK_INTERVAL:
                    log_system_resources()
                    last_resource_check = current_time

                # --- Log de progression major toutes les heures ---
                if current_time - last_major_log > 3600:  # 1h
                    elapsed_hours = (current_time - start_time) / 3600
                    logger.info(f"[WHISPER] Transcription en cours depuis {elapsed_hours:.1f}h - PID: {process.pid} - Segments: {progress_count}")
                    last_major_log = current_time

                # --- Vérification de blocage (2h au lieu de 1h) ---
                if current_time - last_activity_time > ACTIVITY_TIMEOUT:
                    elapsed_hours = (current_time - start_time) / 3600
                    logger.warning(f"[WHISPER] Aucune activité depuis {ACTIVITY_TIMEOUT/60:.0f} minutes (durée totale: {elapsed_hours:.1f}h) - PID: {process.pid}")
                    # On ne fait que logger, on ne tue pas le processus
                    last_activity_time = current_time
                    
                # --- Heartbeat du processus toutes les 3 minutes ---
                if current_time - last_progress_update > PROCESS_HEARTBEAT_INTERVAL:
                    elapsed_hours = (current_time - start_time) / 3600
                    logger.info(f"[WHISPER] Heartbeat - Transcription active depuis {elapsed_hours:.1f}h - PID: {process.pid} - Segments: {progress_count}")
                    last_progress_update = current_time
                    
                # --- Keepalive Coolify toutes les minutes ---
                if current_time - last_progress_update > COOLIFY_KEEPALIVE_INTERVAL:
                    # Forcer un log pour maintenir l'activité
                    logger.debug(f"[COOLIFY] Keepalive - PID: {process.pid} - Segments: {progress_count}")
                    last_progress_update = current_time

                # --- Timeout global augmenté à 24h ---
                if current_time - start_time > MAX_TRANSCRIPTION_TIME:
                    elapsed_hours = (current_time - start_time) / 3600
                    logger.error(f"[WHISPER] Timeout global dépassé ({elapsed_hours:.1f}h) - PID: {process.pid}")
                    try:
                        process.terminate()  # Terminate avant kill
                        time.sleep(5)
                        if process.poll() is None:
                            process.kill()
                    except:
                        pass
                    update_task_progress(task_id, 100, "error")
                    if task_id in ASYNC_TASKS:
                        ASYNC_TASKS[task_id]["result"] = f"Timeout global dépassé ({elapsed_hours:.1f}h)"
                    break

                # --- Surveillance active du process ---
                if process.poll() is not None:
                    elapsed_hours = (current_time - start_time) / 3600
                    logger.info(f"[WHISPER] Processus terminé avec code: {process.returncode} après {elapsed_hours:.1f}h (PID: {process.pid})")
                    if process.returncode != 0:
                        update_task_progress(task_id, 100, "error")
                        if task_id in ASYNC_TASKS:
                            ASYNC_TASKS[task_id]["result"] = f"Processus Whisper terminé anormalement (code {process.returncode})"
                    else:
                        update_task_progress(task_id, 90, "finalizing")
                    break

                if stdout_line:
                    last_activity_time = current_time  # Activité détectée
                    stdout_lines.append(stdout_line.strip())
                    line_content = stdout_line.strip()
                    
                    # Log debug seulement pour les lignes importantes
                    if any(keyword in line_content.lower() for keyword in ["error", "warning", "progress"]):
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

                        # Log tous les 500 segments au lieu de 100
                        if progress_count % 500 == 0:
                            elapsed_hours = (current_time - start_time) / 3600
                            logger.info(f"[WHISPER] Progression: {progress_count} segments traités après {elapsed_hours:.1f}h (PID: {process.pid})")

                        # Mise à jour moins fréquente: tous les 5% et max 1 toutes les 5 secondes
                        if (estimated_progress - ASYNC_TASKS.get(task_id, {}).get("progress", 0) >= 5) and (time.time() - last_progress_update > 5.0):
                            update_task_progress(task_id, int(estimated_progress))
                            last_progress_update = time.time()

                    # Détecter les pourcentages dans les logs si disponibles
                    percentage_match = re.search(r"(\d+)%", line_content)
                    if percentage_match:
                        whisper_progress = int(percentage_match.group(1))
                        # Mapper le pourcentage de Whisper sur notre échelle 25-90%
                        our_progress = 25 + (whisper_progress * 65 / 100)
                        if time.time() - last_progress_update > 5.0:
                            update_task_progress(task_id, int(our_progress))
                            last_progress_update = time.time()

                if stderr_line:
                    last_activity_time = current_time  # Activité détectée aussi sur stderr
                    stderr_lines.append(stderr_line.strip())
                    line_content = stderr_line.strip()
                    
                    # Log seulement les erreurs et avertissements importants
                    if any(keyword in line_content.lower() for keyword in ["error", "warning", "failed"]):
                        logger.warning(f"[WHISPER] STDERR: {line_content}")

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

            # Phase finale - SUPPRESSION DU TIMEOUT SUBPROCESS
            update_task_progress(task_id, 90, "finalizing")
            
            # PAS DE TIMEOUT sur communicate() pour permettre transcriptions très longues
            remaining_stdout, remaining_stderr = process.communicate()  # timeout supprimé!
            stdout_lines.extend(remaining_stdout.splitlines())
            stderr_lines.extend(remaining_stderr.splitlines())

        except Exception as e:
            logger.error(f"[WHISPER] Exception dans la boucle de monitoring: {e}")
            try:
                process.terminate()
                time.sleep(3)
                if process.poll() is None:
                    process.kill()
            except:
                pass
            raise

        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)
        result = subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)

    finally:
        try:
            os.unlink(temp_file_path)
        except:
            pass

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
        f"[WHISPER] Fin run_whisper_transcription, durée: {processing_time/3600:.2f}h ({processing_time:.0f}s)"
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
            "version": "1.0.0-longue-duree",
            "max_transcription_hours": MAX_TRANSCRIPTION_TIME / 3600,
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
            "max_duration_hours": MAX_TRANSCRIPTION_TIME / 3600,
        }
    )


@app.route("/reset-transcriptions", methods=["POST"])
def reset_transcriptions():
    """Réinitialiser le compteur de transcriptions actives (debug)"""
    global ACTIVE_TRANSCRIPTIONS, ASYNC_TASKS
    
    # Nettoyer les tâches fantômes (plus de 25h pour laisser marge aux longues transcriptions)
    current_time = time.time()
    tasks_to_remove = []
    
    for task_id, task in ASYNC_TASKS.items():
        if task.get("status") == "processing":
            created_time = datetime.fromisoformat(task.get("created_at", "2020-01-01T00:00:00"))
            if (current_time - created_time.timestamp()) > 90000:  # 25h
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

    # Calculer la durée écoulée
    created_at = task.get("created_at")
    elapsed_time = None
    if created_at:
        try:
            created_time = datetime.fromisoformat(created_at)
            elapsed_seconds = (datetime.now() - created_time).total_seconds()
            elapsed_time = f"{elapsed_seconds/3600:.1f}h"
        except:
            pass

    response = {
        "task_id": task_id,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "created_at": created_at,
        "elapsed_time": elapsed_time,
        "max_duration_hours": MAX_TRANSCRIPTION_TIME / 3600,
    }

    # Ajouter le résultat si la tâche est terminée
    if task["status"] in ["completed", "error"]:
        response["result"] = task.get("result")

    return jsonify(response)


@app.route("/transcriptions/<filename>", methods=["GET"])
def download_transcription(filename):
    """Télécharger un fichier de transcription"""
    output_dir = "/var/log/whisper"
    file_path = os.path.join(output_dir, filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "Fichier non trouvé"}), 404
    
    return send_from_directory(output_dir, filename, as_attachment=True)


@app.route("/tasks", methods=["GET"])
def list_tasks():
    """Lister toutes les tâches asynchrones"""
    tasks = []
    for task_id, task in ASYNC_TASKS.items():
        task_info = {
            "task_id": task_id,
            "status": task["status"],
            "progress": task.get("progress", 0),
            "created_at": task.get("created_at"),
        }
        
        # Calculer la durée écoulée
        created_at = task.get("created_at")
        if created_at:
            try:
                created_time = datetime.fromisoformat(created_at)
                elapsed_seconds = (datetime.now() - created_time).total_seconds()
                task_info["elapsed_time"] = f"{elapsed_seconds/3600:.1f}h"
            except:
                pass
        
        # Ajouter le résultat si la tâche est terminée
        if task["status"] in ["completed", "error"]:
            task_info["result"] = task.get("result")
        
        tasks.append(task_info)
    
    return jsonify({
        "tasks": tasks,
        "total": len(tasks),
        "active_transcriptions": ACTIVE_TRANSCRIPTIONS
    })


if __name__ == "__main__":
    # Nettoyer les anciennes transcriptions au démarrage
    cleanup_old_transcriptions()
    
    print("🚀 Démarrage du service Whisper - La Boîte de Chocolat")
    print(f"📁 Whisper path: {WHISPER_PATH}")
    print(f"🤖 Modèle: {os.path.basename(MODEL_PATH)}")
    print(f"⏱️  Timeout max: {MAX_TRANSCRIPTION_TIME/3600:.1f}h")
    print(f"🔄 Transcriptions concurrentes max: {MAX_CONCURRENT_TRANSCRIPTIONS}")
    print("=" * 60)
    
    # Démarrer le serveur Flask
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
        threaded=True,
        use_reloader=False
    )
