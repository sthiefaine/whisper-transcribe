#!/usr/bin/env python3
"""
Proxy server pour normaliser les noms de modèles avant de les envoyer à Scriberr
Résout le problème où "V3-large" doit être converti en "large-v3"
"""

import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from functools import wraps
import json

# Configuration
SCRIBERR_URL = os.getenv("SCRIBERR_URL", "http://scriberr:8080")
PORT = int(os.getenv("PORT", "8080"))

app = Flask(__name__)
CORS(app, origins=["*"])

def normalize_model_name(model: str) -> str:
    """
    Normalise le nom du modèle pour WhisperX/Scriberr
    Convertit "V3-large" -> "large-v3", etc.
    """
    if not model:
        return model
    
    model_lower = model.lower().strip()
    
    # Mapping des variantes vers le format standard WhisperX
    model_mapping = {
        "v3-large": "large-v3",
        "v3_large": "large-v3",
        "largev3": "large-v3",
        "large_v3": "large-v3",
        "v2-large": "large-v2",
        "v2_large": "large-v2",
        "largev2": "large-v2",
        "large_v2": "large-v2",
        "v1-large": "large-v1",
        "v1_large": "large-v1",
        "largev1": "large-v1",
        "large_v1": "large-v1",
    }
    
    # Appliquer le mapping si nécessaire
    if model_lower in model_mapping:
        normalized = model_mapping[model_lower]
        print(f"🔄 Normalisation du modèle: '{model}' -> '{normalized}'")
        return normalized
    
    # Si déjà au bon format, retourner tel quel
    return model

def proxy_request_to_scriberr(endpoint: str, method: str = "GET", **kwargs):
    """Proxy une requête vers Scriberr"""
    url = f"{SCRIBERR_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=30, **kwargs)
        elif method.upper() == "POST":
            response = requests.post(url, timeout=300, **kwargs)
        elif method.upper() == "PUT":
            response = requests.put(url, timeout=30, **kwargs)
        elif method.upper() == "DELETE":
            response = requests.delete(url, timeout=30, **kwargs)
        else:
            return jsonify({"error": f"Méthode {method} non supportée"}), 405
        
        # Retourner la réponse de Scriberr
        try:
            return response.json(), response.status_code
        except:
            return response.text, response.status_code
            
    except requests.exceptions.ConnectionError:
        return jsonify({"error": f"Impossible de se connecter à Scriberr à {SCRIBERR_URL}"}), 503
    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout lors de la connexion à Scriberr"}), 504
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la communication avec Scriberr: {str(e)}"}), 500

@app.route("/health", methods=["GET"])
def health():
    """Health check qui vérifie aussi Scriberr"""
    try:
        scriberr_response = requests.get(f"{SCRIBERR_URL}/health", timeout=5)
        scriberr_healthy = scriberr_response.status_code == 200
    except:
        scriberr_healthy = False
    
    return jsonify({
        "status": "healthy" if scriberr_healthy else "degraded",
        "proxy": "ok",
        "scriberr": "ok" if scriberr_healthy else "unreachable"
    }), 200 if scriberr_healthy else 503

@app.route("/transcribe", methods=["POST"])
def transcribe():
    """Proxy pour /transcribe avec normalisation du modèle"""
    try:
        # Récupérer les données de la requête
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Normaliser le nom du modèle si présent
        if "model" in data:
            original_model = data["model"]
            data["model"] = normalize_model_name(data["model"])
            if original_model != data["model"]:
                print(f"✅ Modèle normalisé: '{original_model}' -> '{data['model']}'")
        
        # Envoyer à Scriberr
        if request.is_json:
            response = requests.post(
                f"{SCRIBERR_URL}/transcribe",
                json=data,
                timeout=300
            )
        else:
            # Pour multipart/form-data (fichiers)
            files = {}
            if "audio_file" in request.files:
                files["audio_file"] = request.files["audio_file"]
            
            response = requests.post(
                f"{SCRIBERR_URL}/transcribe",
                data=data,
                files=files,
                timeout=300
            )
        
        try:
            return response.json(), response.status_code
        except:
            return response.text, response.status_code
            
    except Exception as e:
        return jsonify({"error": f"Erreur: {str(e)}"}), 500

@app.route("/transcribe-async", methods=["POST"])
def transcribe_async():
    """Proxy pour /transcribe-async avec normalisation du modèle"""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        # Normaliser le nom du modèle
        if "model" in data:
            original_model = data["model"]
            data["model"] = normalize_model_name(data["model"])
            if original_model != data["model"]:
                print(f"✅ Modèle normalisé: '{original_model}' -> '{data['model']}'")
        
        # Envoyer à Scriberr
        response = requests.post(
            f"{SCRIBERR_URL}/transcribe-async",
            json=data if request.is_json else None,
            data=data if not request.is_json else None,
            timeout=30
        )
        
        try:
            return response.json(), response.status_code
        except:
            return response.text, response.status_code
            
    except Exception as e:
        return jsonify({"error": f"Erreur: {str(e)}"}), 500

@app.route("/status/<task_id>", methods=["GET"])
def get_status(task_id):
    """Proxy pour /status/<task_id>"""
    return proxy_request_to_scriberr(f"/status/{task_id}", "GET")

@app.route("/models", methods=["GET"])
def get_models():
    """Proxy pour /models"""
    return proxy_request_to_scriberr("/models", "GET")

@app.route("/tasks", methods=["GET"])
def get_tasks():
    """Proxy pour /tasks"""
    return proxy_request_to_scriberr("/tasks", "GET")

@app.route("/list", methods=["GET"])
def list_transcriptions():
    """Proxy pour /list"""
    return proxy_request_to_scriberr("/list", "GET")

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    """Proxy pour /download/<filename>"""
    try:
        response = requests.get(
            f"{SCRIBERR_URL}/download/{filename}",
            stream=True,
            timeout=60
        )
        
        if response.status_code == 200:
            from flask import Response
            return Response(
                response.iter_content(chunk_size=8192),
                mimetype=response.headers.get("Content-Type", "application/octet-stream"),
                headers={
                    "Content-Disposition": response.headers.get("Content-Disposition", f"attachment; filename={filename}")
                }
            )
        else:
            return response.text, response.status_code
            
    except Exception as e:
        return jsonify({"error": f"Erreur: {str(e)}"}), 500

# Proxy toutes les autres routes vers Scriberr
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy_all(path):
    """Proxy toutes les autres routes vers Scriberr"""
    method = request.method
    
    # Normaliser le modèle dans les requêtes POST/PUT
    if method in ["POST", "PUT", "PATCH"]:
        try:
            if request.is_json:
                data = request.get_json()
                if data and "model" in data:
                    original_model = data["model"]
                    data["model"] = normalize_model_name(data["model"])
                    if original_model != data["model"]:
                        print(f"✅ Modèle normalisé: '{original_model}' -> '{data['model']}'")
                
                response = requests.request(
                    method,
                    f"{SCRIBERR_URL}/{path}",
                    json=data,
                    params=request.args,
                    timeout=300
                )
            else:
                data = request.form.to_dict()
                if "model" in data:
                    original_model = data["model"]
                    data["model"] = normalize_model_name(data["model"])
                    if original_model != data["model"]:
                        print(f"✅ Modèle normalisé: '{original_model}' -> '{data['model']}'")
                
                files = {}
                if request.files:
                    files = {k: v for k, v in request.files.items()}
                
                response = requests.request(
                    method,
                    f"{SCRIBERR_URL}/{path}",
                    data=data,
                    files=files if files else None,
                    params=request.args,
                    timeout=300
                )
        except Exception as e:
            return jsonify({"error": f"Erreur: {str(e)}"}), 500
    else:
        response = requests.request(
            method,
            f"{SCRIBERR_URL}/{path}",
            params=request.args,
            timeout=30
        )
    
    try:
        return response.json(), response.status_code
    except:
        return response.text, response.status_code

if __name__ == "__main__":
    print("🚀 Proxy Server pour Scriberr")
    print(f"📡 Scriberr URL: {SCRIBERR_URL}")
    print(f"🌐 Proxy écoute sur le port {PORT}")
    print("✅ Normalisation automatique des noms de modèles activée")
    print("   Exemples: 'V3-large' -> 'large-v3', 'v3-large' -> 'large-v3'")
    
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        threaded=True
    )
