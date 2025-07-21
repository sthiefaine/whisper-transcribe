#!/usr/bin/env python3
"""
Service de transcription audio Whisper.cpp pour La Boîte de Chocolat
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

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["*"])  # En production, spécifiez vos domaines

# Configuration
WHISPER_PATH = "/opt/whisper.cpp"
MODEL_PATH = f"{WHISPER_PATH}/models/ggml-base.bin"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB max

# Dictionnaire global pour stocker l'état des tâches asynchrones
ASYNC_TASKS = {}

# Compteur global pour les transcriptions actives
ACTIVE_TRANSCRIPTIONS = 0
MAX_CONCURRENT_TRANSCRIPTIONS = 1

# Fonction worker pour la transcription asynchrone

def async_transcription_worker(task_id, audio_url, language, model, output_format='txt', prompt=None):
    global ACTIVE_TRANSCRIPTIONS
    try:
        ASYNC_TASKS[task_id]['status'] = 'processing'
        ASYNC_TASKS[task_id]['progress'] = 0
        # Télécharger l'audio (copie de la logique existante)
        import tempfile, requests, os, uuid, urllib.parse, re
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            response = requests.get(audio_url, stream=True, timeout=30)
            response.raise_for_status()
            file_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
                file_size += len(chunk)
            temp_file_path = temp_file.name
        # Construire la commande Whisper
        model_path = f"{WHISPER_PATH}/models/ggml-{model}.bin"
        if not os.path.exists(model_path):
            model_path = MODEL_PATH
        cmd = build_whisper_cmd(
            WHISPER_PATH,
            model_path,
            temp_file_path,
            language,
            output_format,
            prompt=prompt,
            no_timestamps=(output_format == "txt")
        )
        import subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WHISPER_PATH,
            bufsize=1,
            universal_newlines=True
        )
        # Lire la sortie en temps réel pour la progression
        percent = 0
        progress_re = re.compile(r'(\d{1,3})%')
        while True:
            line = process.stdout.readline() if process.stdout else None
            if not line:
                if process.poll() is not None:
                    break
                continue
            # Chercher un pourcentage dans la ligne
            match = progress_re.search(line)
            if match:
                percent = int(match.group(1))
                ASYNC_TASKS[task_id]['progress'] = percent
        process.communicate()
        os.unlink(temp_file_path)
        # Chercher le fichier de sortie
        parsed_url = urllib.parse.urlparse(audio_url)
        audio_base = os.path.splitext(os.path.basename(parsed_url.path))[0]
        transcription_id = str(uuid.uuid4())
        output_dir = "/var/log/whisper"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{audio_base}__{transcription_id}.{output_format}")
        # Le whisper-cli sort le .txt dans le dossier courant
        whisper_output = os.path.join(WHISPER_PATH, os.path.basename(temp_file_path).replace('.mp3', f'.{output_format}'))
        transcription = None
        if os.path.exists(whisper_output):
            with open(whisper_output, 'r', encoding='utf-8') as f:
                transcription = f.read().strip()
            os.unlink(whisper_output)
        elif process.stdout and process.stdout:
            # Si le fichier n'existe pas mais qu'on a du texte sur STDOUT, l'utiliser
            process.stdout.seek(0)
            transcription = process.stdout.read().strip()
        elif process.stderr and process.stderr:
            process.stderr.seek(0)
            transcription = process.stderr.read().strip()
        if transcription:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(transcription)
            ASYNC_TASKS[task_id]['status'] = 'done'
            ASYNC_TASKS[task_id]['progress'] = 100
            ASYNC_TASKS[task_id]['result'] = f"/transcriptions/{audio_base}__{transcription_id}.{output_format}"
        else:
            ASYNC_TASKS[task_id]['status'] = 'error'
            ASYNC_TASKS[task_id]['result'] = "Fichier de sortie non trouvé et STDOUT vide"
    except Exception as e:
        ASYNC_TASKS[task_id]['status'] = 'error'
        ASYNC_TASKS[task_id]['result'] = str(e)
    finally:
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
    prompt=None,
    no_timestamps=False
):
    cmd = [
        f"{whisper_path}/build/bin/whisper-cli",
        "-m", model_path,
        "-f", temp_file_path,
        "-l", language,
        f"-o{output_format}",
    ]
    if no_timestamps and output_format == "txt":
        cmd.append("--no-timestamps")
    if prompt:
        cmd += ["--prompt", prompt]
    return cmd

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de santé pour les health checks"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model": "whisper-base-fr",
        "version": "1.0.0"
    })

@app.route('/models', methods=['GET'])
def list_models():
    """Lister les modèles disponibles"""
    models_dir = f"{WHISPER_PATH}/models"
    models = []
    
    if os.path.exists(models_dir):
        for file in os.listdir(models_dir):
            if file.endswith('.bin'):
                models.append(file)
    
    return jsonify({
        "models": models,
        "current_model": os.path.basename(MODEL_PATH)
    })

@app.route('/transcribe', methods=['POST'])
def transcribe():
    global ACTIVE_TRANSCRIPTIONS
    start_time = time.time()
    
    # Vérifier si une transcription est déjà en cours
    if ACTIVE_TRANSCRIPTIONS >= MAX_CONCURRENT_TRANSCRIPTIONS:
        return jsonify({"error": "Transcription en cours, veuillez réessayer dans quelques minutes"}), 429
    
    try:
        ACTIVE_TRANSCRIPTIONS += 1
        data = request.get_json()
        if not data:
            return jsonify({"error": "Données JSON requises"}), 400
        
        audio_url = data.get('audio_url')
        language = data.get('language', 'fr')
        model = data.get('model', 'base')
        output_format = data.get('output_format', 'txt').lower()
        
        if not audio_url:
            return jsonify({"error": "audio_url requis"}), 400

        logger.info(f"🎯 Début transcription URL: {audio_url}")
        logger.info(f"🔧 Paramètres: langue={language}, modèle={model}")

        # Télécharger l'audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            response = requests.get(audio_url, stream=True, timeout=30)
            response.raise_for_status()
            
            file_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if file_size > MAX_FILE_SIZE:
                    os.unlink(temp_file.name)
                    return jsonify({"error": "Fichier trop volumineux (max 100MB)"}), 400
                
                temp_file.write(chunk)
                file_size += len(chunk)
            
            temp_file_path = temp_file.name

        logger.info(f"Fichier téléchargé: {temp_file_path} ({file_size} bytes)")

        # Construire la commande Whisper
        model_path = f"{WHISPER_PATH}/models/ggml-{model}.bin"
        if not os.path.exists(model_path):
            model_path = MODEL_PATH  # Fallback au modèle par défaut

        cmd = build_whisper_cmd(
            WHISPER_PATH,
            model_path,
            temp_file_path,
            language,
            output_format,
            prompt=data.get('prompt') if 'data' in locals() and data else None,
            no_timestamps=(output_format == "txt")
        )
        
        logger.info(f"Exécution: {' '.join(cmd)}")
        
        # Exécuter Whisper avec logs de progression détaillés
        logger.info(f"🚀 Début exécution Whisper avec modèle {model}...")
        logger.info(f"📋 Commande: {' '.join(cmd)}")
        
        # Utiliser Popen pour avoir plus de contrôle et voir les logs en temps réel
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WHISPER_PATH,
            bufsize=1,
            universal_newlines=True
        )
        
        # Logs de progression améliorés
        start_time_whisper = time.time()
        logger.info(f"🔄 Processus Whisper démarré (PID: {process.pid})")
        
        try:
            # Lire la sortie en temps réel pour voir la progression
            stdout_lines = []
            stderr_lines = []
            progress_count = 0
            
            # Lire stdout et stderr en temps réel
            while True:
                stdout_line = process.stdout.readline() if process.stdout else None
                stderr_line = process.stderr.readline() if process.stderr else None
                
                if stdout_line:
                    stdout_lines.append(stdout_line.strip())
                    line_content = stdout_line.strip()
                    
                    # Log de progression en temps réel avec plus de détails
                    if any(keyword in line_content.lower() for keyword in ["progress", "%", "segment", "frame"]):
                        progress_count += 1
                        elapsed = time.time() - start_time_whisper
                        logger.info(f"📊 PROGRESSION [{elapsed:.1f}s] #{progress_count}: {line_content}")
                    elif "whisper" in line_content.lower() and len(line_content) > 20:
                        logger.info(f"🎤 WHISPER: {line_content[:150]}...")
                    elif len(line_content) > 10 and not line_content.startswith('['):
                        # Log des lignes de transcription (éviter les logs de debug)
                        logger.info(f"📝 TRANSCRIPTION: {line_content[:100]}...")
                
                if stderr_line:
                    stderr_lines.append(stderr_line.strip())
                    line_content = stderr_line.strip()
                    
                    # Log des erreurs et infos de debug avec plus de contexte
                    if any(keyword in line_content.lower() for keyword in ["error", "failed", "exception"]):
                        logger.error(f"❌ WHISPER ERROR: {line_content}")
                    elif any(keyword in line_content.lower() for keyword in ["info", "debug", "warning"]):
                        logger.info(f"ℹ️  WHISPER INFO: {line_content}")
                    elif "loading" in line_content.lower() or "initializing" in line_content.lower():
                        logger.info(f"⚙️  INIT: {line_content}")
                    elif "processing" in line_content.lower():
                        logger.info(f"🔄 PROCESSING: {line_content}")
                
                # Vérifier si le processus est terminé
                if process.poll() is not None:
                    break
            
            # Lire le reste de la sortie
            remaining_stdout, remaining_stderr = process.communicate()
            stdout_lines.extend(remaining_stdout.splitlines())
            stderr_lines.extend(remaining_stderr.splitlines())
            
            stdout = '\n'.join(stdout_lines)
            stderr = '\n'.join(stderr_lines)
            result = subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
            
            elapsed_time = time.time() - start_time_whisper
            logger.info(f"✅ Whisper terminé en {elapsed_time:.2f}s (returncode: {process.returncode})")
            logger.info(f"📈 {progress_count} logs de progression capturés")
            
            # Log des sorties finales pour debug
            if stdout:
                logger.info(f"📄 STDOUT FINAL ({len(stdout)} chars): {stdout[:300]}...")
            if stderr:
                logger.info(f"⚠️  STDERR FINAL ({len(stderr)} chars): {stderr[:300]}...")
                
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Timeout après {time.time() - start_time_whisper:.2f}s")
            process.kill()
            raise
        
        # Nettoyer le fichier temporaire
        os.unlink(temp_file_path)
        
        if result.returncode != 0:
            logger.error(f"Erreur Whisper: {result.stderr}")
            return jsonify({"error": f"Erreur transcription: {result.stderr}"}), 500

        # Utiliser la sortie STDOUT de Whisper directement
        transcription = None
        base_filename = os.path.basename(temp_file_path)
        ext = f'.{output_format}'
        output_filename = base_filename.replace('.mp3', ext)
        output_file = os.path.join(WHISPER_PATH, output_filename)
        logger.info(f"Recherche du fichier de sortie: {output_file}")
        logger.info(f"Fichier existe: {os.path.exists(output_file)}")
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                transcription = f.read().strip()
            os.unlink(output_file)
        elif result.stdout and result.stdout.strip():
            transcription = result.stdout.strip()
        else:
            return jsonify({"error": "Fichier de sortie non trouvé et STDOUT vide"}), 500

        processing_time = time.time() - start_time
        
        logger.info(f"Transcription terminée en {processing_time:.2f}s")

        # Nettoyer les anciens fichiers
        cleanup_old_transcriptions()
        # Si la transcription est longue, la stocker et renvoyer une URL
        if len(transcription) > 2000:
            # Extraire le nom de base du fichier audio depuis l'URL
            import urllib.parse
            parsed_url = urllib.parse.urlparse(audio_url)
            audio_base = os.path.splitext(os.path.basename(parsed_url.path))[0]
            transcription_id = str(uuid.uuid4())
            output_dir = "/var/log/whisper"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{audio_base}__{transcription_id}.{output_format}")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(transcription)
            transcription_url = request.url_root.rstrip('/') + f"/transcriptions/{audio_base}__{transcription_id}.{output_format}"
            return jsonify({
                "success": True,
                "transcription_url": transcription_url,
                "model": f"whisper-{model}-{language}",
                "processing_time": processing_time,
                "file_size": file_size
            })
        else:
            return jsonify({
                "success": True,
                "transcription": transcription,
                "model": f"whisper-{model}-{language}",
                "processing_time": processing_time,
                "file_size": file_size
            })

    except subprocess.TimeoutExpired:
        logger.error("Timeout lors de la transcription")
        return jsonify({"error": "Timeout lors de la transcription"}), 408
        
    except requests.RequestException as e:
        logger.error(f"Erreur téléchargement: {e}")
        return jsonify({"error": f"Erreur téléchargement: {str(e)}"}), 400
        
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        ACTIVE_TRANSCRIPTIONS -= 1

@app.route('/transcribe/file', methods=['POST'])
def transcribe_file():
    global ACTIVE_TRANSCRIPTIONS
    start_time = time.time()
    
    # Vérifier si une transcription est déjà en cours
    if ACTIVE_TRANSCRIPTIONS >= MAX_CONCURRENT_TRANSCRIPTIONS:
        return jsonify({"error": "Transcription en cours, veuillez réessayer dans quelques minutes"}), 429
    
    try:
        ACTIVE_TRANSCRIPTIONS += 1
        # Vérifier qu'un fichier a été envoyé
        if 'audio_file' not in request.files:
            return jsonify({"error": "Aucun fichier audio fourni"}), 400
        
        audio_file = request.files['audio_file']
        if audio_file.filename == '':
            return jsonify({"error": "Aucun fichier sélectionné"}), 400
        
        # Récupérer les paramètres
        language = request.form.get('language', 'fr')
        model = request.form.get('model', 'base')
        output_format = request.form.get('output_format', 'txt').lower()
        
        logger.info(f"Début transcription fichier: {audio_file.filename}")

        # Sauvegarder le fichier temporairement
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            audio_file.save(temp_file.name)
            temp_file_path = temp_file.name
            
            # Obtenir la taille du fichier
            file_size = os.path.getsize(temp_file_path)

        logger.info(f"Fichier sauvegardé: {temp_file_path} ({file_size} bytes)")

        # Construire la commande Whisper
        model_path = f"{WHISPER_PATH}/models/ggml-{model}.bin"
        if not os.path.exists(model_path):
            model_path = MODEL_PATH  # Fallback au modèle par défaut

        cmd = build_whisper_cmd(
            WHISPER_PATH,
            model_path,
            temp_file_path,
            language,
            output_format,
            prompt=request.form.get('prompt'),
            no_timestamps=(output_format == "txt")
        )
        
        logger.info(f"Exécution: {' '.join(cmd)}")
        
        # Exécuter Whisper avec logs de progression détaillés
        logger.info(f"🚀 Début exécution Whisper avec modèle {model}...")
        logger.info(f"📋 Commande: {' '.join(cmd)}")
        
        # Utiliser Popen pour avoir plus de contrôle et voir les logs en temps réel
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WHISPER_PATH,
            bufsize=1,
            universal_newlines=True
        )
        
        # Logs de progression améliorés
        start_time_whisper = time.time()
        logger.info(f"🔄 Processus Whisper démarré (PID: {process.pid})")
        
        try:
            # Lire la sortie en temps réel pour voir la progression
            stdout_lines = []
            stderr_lines = []
            progress_count = 0
            
            # Lire stdout et stderr en temps réel
            while True:
                stdout_line = process.stdout.readline() if process.stdout else None
                stderr_line = process.stderr.readline() if process.stderr else None
                
                if stdout_line:
                    stdout_lines.append(stdout_line.strip())
                    line_content = stdout_line.strip()
                    
                    # Log de progression en temps réel avec plus de détails
                    if any(keyword in line_content.lower() for keyword in ["progress", "%", "segment", "frame"]):
                        progress_count += 1
                        elapsed = time.time() - start_time_whisper
                        logger.info(f"📊 PROGRESSION [{elapsed:.1f}s] #{progress_count}: {line_content}")
                    elif "whisper" in line_content.lower() and len(line_content) > 20:
                        logger.info(f"🎤 WHISPER: {line_content[:150]}...")
                    elif len(line_content) > 10 and not line_content.startswith('['):
                        # Log des lignes de transcription (éviter les logs de debug)
                        logger.info(f"📝 TRANSCRIPTION: {line_content[:100]}...")
                
                if stderr_line:
                    stderr_lines.append(stderr_line.strip())
                    line_content = stderr_line.strip()
                    
                    # Log des erreurs et infos de debug avec plus de contexte
                    if any(keyword in line_content.lower() for keyword in ["error", "failed", "exception"]):
                        logger.error(f"❌ WHISPER ERROR: {line_content}")
                    elif any(keyword in line_content.lower() for keyword in ["info", "debug", "warning"]):
                        logger.info(f"ℹ️  WHISPER INFO: {line_content}")
                    elif "loading" in line_content.lower() or "initializing" in line_content.lower():
                        logger.info(f"⚙️  INIT: {line_content}")
                    elif "processing" in line_content.lower():
                        logger.info(f"🔄 PROCESSING: {line_content}")
                
                # Vérifier si le processus est terminé
                if process.poll() is not None:
                    break
            
            # Lire le reste de la sortie
            remaining_stdout, remaining_stderr = process.communicate()
            stdout_lines.extend(remaining_stdout.splitlines())
            stderr_lines.extend(remaining_stderr.splitlines())
            
            stdout = '\n'.join(stdout_lines)
            stderr = '\n'.join(stderr_lines)
            result = subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
            
            elapsed_time = time.time() - start_time_whisper
            logger.info(f"✅ Whisper terminé en {elapsed_time:.2f}s (returncode: {process.returncode})")
            logger.info(f"📈 {progress_count} logs de progression capturés")
            
            # Log des sorties finales pour debug
            if stdout:
                logger.info(f"📄 STDOUT FINAL ({len(stdout)} chars): {stdout[:300]}...")
            if stderr:
                logger.info(f"⚠️  STDERR FINAL ({len(stderr)} chars): {stderr[:300]}...")
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout après {time.time() - start_time_whisper:.2f}s")
            process.kill()
            raise
        
        # Nettoyer le fichier temporaire
        os.unlink(temp_file_path)
        
        if result.returncode != 0:
            logger.error(f"Erreur Whisper: {result.stderr}")
            return jsonify({"error": f"Erreur transcription: {result.stderr}"}), 500

        # Utiliser la sortie STDOUT de Whisper directement
        transcription = None
        if result.stdout and result.stdout.strip() and output_format == 'txt':
            transcription = result.stdout.strip()
            logger.info(f"Transcription récupérée depuis STDOUT: {len(transcription)} caractères")
        else:
            # Fallback: chercher le fichier de sortie
            base_filename = os.path.basename(temp_file_path)
            ext = f'.{output_format}'
            output_filename = base_filename.replace('.mp3', ext)
            output_file = os.path.join(WHISPER_PATH, output_filename)
            
            logger.info(f"Recherche du fichier de sortie: {output_file}")
            logger.info(f"Fichier existe: {os.path.exists(output_file)}")
            
            # Lister les fichiers dans le répertoire WHISPER_PATH pour debug
            if os.path.exists(WHISPER_PATH):
                files_in_dir = os.listdir(WHISPER_PATH)
                logger.info(f"Fichiers dans {WHISPER_PATH}: {files_in_dir}")
            
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    transcription = f.read().strip()
                os.unlink(output_file)
            else:
                return jsonify({"error": "Fichier de sortie non trouvé et STDOUT vide"}), 500

        processing_time = time.time() - start_time
        logger.info(f"Transcription terminée en {processing_time:.2f}s")

        # Nettoyer les anciens fichiers
        cleanup_old_transcriptions()
        # Si la transcription est longue, la stocker et renvoyer une URL
        if len(transcription) > 2000:
            audio_filename = audio_file.filename or "audio"
            audio_base = os.path.splitext(secure_filename(audio_filename))[0]
            transcription_id = str(uuid.uuid4())
            output_dir = "/var/log/whisper"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{audio_base}__{transcription_id}.{output_format}")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(transcription)
            transcription_url = request.url_root.rstrip('/') + f"/transcriptions/{audio_base}__{transcription_id}.{output_format}"
            return jsonify({
                "success": True,
                "transcription_url": transcription_url,
                "model": f"whisper-{model}-{language}",
                "processing_time": processing_time,
                "file_size": file_size,
                "filename": audio_file.filename
            })
        else:
            return jsonify({
                "success": True,
                "transcription": transcription,
                "model": f"whisper-{model}-{language}",
                "processing_time": processing_time,
                "file_size": file_size,
                "filename": audio_file.filename
            })

    except subprocess.TimeoutExpired:
        logger.error("Timeout lors de la transcription")
        return jsonify({"error": "Timeout lors de la transcription"}), 408
        
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        ACTIVE_TRANSCRIPTIONS -= 1

@app.route('/transcribe/batch', methods=['POST'])
def transcribe_batch():
    """Transcrire plusieurs fichiers"""
    try:
        data = request.get_json()
        audio_urls = data.get('audio_urls', [])
        
        if not audio_urls:
            return jsonify({"error": "audio_urls requis"}), 400
        
        results = []
        for url in audio_urls:
            try:
                # Utiliser la fonction de transcription existante
                result = transcribe_single(url)
                transcription = result.get("transcription", "") if result and hasattr(result, 'get') else ""
                results.append({
                    "url": url,
                    "success": True,
                    "transcription": transcription
                })
            except Exception as e:
                results.append({
                    "url": url,
                    "success": False,
                    "error": str(e)
                })
        
        return jsonify({
            "success": True,
            "results": results
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def transcribe_single(audio_url):
    """Fonction helper pour transcrire un seul fichier"""
    # Logique de transcription (simplifiée pour l'exemple)
    pass

@app.route('/transcribe-async', methods=['POST'])
def transcribe_async():
    global ACTIVE_TRANSCRIPTIONS
    
    # Vérifier si une transcription est déjà en cours
    if ACTIVE_TRANSCRIPTIONS >= MAX_CONCURRENT_TRANSCRIPTIONS:
        return jsonify({"error": "Transcription en cours, veuillez réessayer dans quelques minutes"}), 429
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Données JSON requises"}), 400
    audio_url = data.get('audio_url')
    language = data.get('language', 'fr')
    model = data.get('model', 'base')
    output_format = data.get('output_format', 'txt').lower()
    prompt = data.get('prompt')
    if not audio_url:
        return jsonify({"error": "audio_url requis"}), 400
    import uuid
    task_id = str(uuid.uuid4())
    ASYNC_TASKS[task_id] = {'status': 'pending', 'result': None, 'progress': 0}
    ACTIVE_TRANSCRIPTIONS += 1
    thread = threading.Thread(target=async_transcription_worker, args=(task_id, audio_url, language, model, output_format, prompt))
    thread.start()
    return jsonify({"task_id": task_id, "status_url": f"/transcription-status/{task_id}"})

@app.route('/transcription-status/<task_id>', methods=['GET'])
def transcription_status(task_id):
    task = ASYNC_TASKS.get(task_id)
    if not task:
        return jsonify({"error": "Tâche inconnue"}), 404
    return jsonify({"status": task['status'], "progress": task.get('progress', 0), "result": task['result']})

@app.route('/transcriptions/<path:transcription_file>', methods=['GET'])
def get_transcription_file(transcription_file):
    output_dir = "/var/log/whisper"
    return send_from_directory(output_dir, transcription_file, as_attachment=True)

if __name__ == '__main__':
    # Vérifier que le modèle existe
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Modèle non trouvé: {MODEL_PATH}")
        exit(1)
    
    logger.info(f"Service Whisper démarré avec le modèle: {MODEL_PATH}")
    app.run(host='0.0.0.0', port=8080, debug=True) 