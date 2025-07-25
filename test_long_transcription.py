#!/usr/bin/env python3
"""
Script de test pour les transcriptions longues
Vérifie que le service ne s'arrête pas silencieusement après 2h
"""

import requests
import json
import time
import sys

# Configuration
API_BASE = "http://localhost:8090"  # Port nginx
# API_BASE = "http://localhost:8080"  # Port direct Flask

def test_health():
    """Test de santé du service"""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Service en santé: {data}")
            return True
        else:
            print(f"❌ Service non disponible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False

def test_async_transcription():
    """Test d'une transcription asynchrone longue"""
    
    # URL d'un podcast long pour tester
    audio_url = "https://stitcher2.acast.com/livestitches/7bcf6793d72ab46ba8d5cb7216d82b0a.mp3?aid=68607828081ac1df5db12c0e&chid=6474db720b87a300106602f9&ci=IlxV7Lei9HgExDXGlVIvP-w1aFySeWo3UpKKPkkj2lt93YkllHa_FA%3D%3D&pf=rss&range=bytes%3D0-&sv=sphinx%401.255.0&uid=1019ffd4e6b596cf73bad1d9e80f8618&Expires=1753205130848&Key-Pair-Id=K38CTQXUSD0VVB&Signature=ViKrb3oL3tcbAUxMuP0IZnd3Jen2Ihi-19Qd0pZW6U0u-G595-eP5cWeMj~xpUNUfjdWgAhttiyYFR2oMD08bEzITbacSr2FUA4ZxCqZ2CxREVs2ZZxiUGbLB4ZWsiKSbE4bW4i3eRBeJW9aCli3IfaXAu8Mxu~JVSDAl~3qEN2JJZa0j1jFm916-izRRQHZh~nNhf9a8M38shEhf1iKH2zVSggEnheWE0SNLfEcAvw-J~RtV0TvyIMT9Jugh-GM-jnphYEDdg7h2O48H0rPnqppdpQYiailLhcZ~wHqY-m-BVspHRoJpSEI35HlmmOu5N2g-tXG1h4weawA4cSEgA__"
    
    payload = {
        "audio_url": audio_url,
        "model": "large-v3",
        "language": "fr",
        "output_format": "srt",
        "word_thold": 0.005,
        "no_speech_thold": 0.40,
        "prompt": "Emission podcast avec des invités sur le film Avatar de 2009, pull-over, enculé, m'accompage, immonde Murray"
    }
    
    print("🚀 Démarrage de la transcription asynchrone...")
    print(f"📡 URL: {API_BASE}/transcribe-async")
    print(f"🎵 Audio: {audio_url[:100]}...")
    
    try:
        response = requests.post(
            f"{API_BASE}/transcribe-async",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            print(f"✅ Transcription démarrée avec succès!")
            print(f"🆔 Task ID: {task_id}")
            print(f"📊 Status URL: {data.get('status_url')}")
            print(f"⏱️  Max duration: {data.get('max_duration_hours')}h")
            return task_id
        else:
            print(f"❌ Erreur lors du démarrage: {response.status_code}")
            print(f"📄 Réponse: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return None

def monitor_transcription(task_id, max_hours=6):
    """Surveiller la progression d'une transcription"""
    
    print(f"\n📊 Surveillance de la transcription {task_id}")
    print(f"⏱️  Durée max de surveillance: {max_hours}h")
    print("=" * 60)
    
    start_time = time.time()
    last_progress = 0
    last_log_time = time.time()
    
    while True:
        try:
            response = requests.get(
                f"{API_BASE}/transcription-status/{task_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                progress = data.get("progress", 0)
                elapsed = data.get("elapsed_time", "N/A")
                
                current_time = time.time()
                elapsed_seconds = current_time - start_time
                elapsed_hours = elapsed_seconds / 3600
                
                # Log toutes les 5 minutes ou si progression
                if (current_time - last_log_time > 300) or (progress != last_progress):
                    print(f"[{elapsed_hours:.1f}h] Status: {status} | Progress: {progress}% | Elapsed: {elapsed}")
                    last_log_time = current_time
                    last_progress = progress
                
                # Vérifier si terminé
                if status in ["completed", "error"]:
                    print(f"\n🏁 Transcription terminée!")
                    print(f"📊 Status final: {status}")
                    print(f"📈 Progression finale: {progress}%")
                    print(f"⏱️  Durée totale: {elapsed_hours:.1f}h")
                    
                    if status == "completed":
                        result = data.get("result", {})
                        if isinstance(result, dict):
                            transcription_url = result.get("transcription_url")
                            if transcription_url:
                                print(f"📄 Fichier disponible: {API_BASE}{transcription_url}")
                        print("✅ Transcription réussie!")
                    else:
                        print(f"❌ Erreur: {data.get('result', 'Erreur inconnue')}")
                    
                    return status == "completed"
                
                # Vérifier le timeout de surveillance
                if elapsed_hours > max_hours:
                    print(f"\n⏰ Timeout de surveillance atteint ({max_hours}h)")
                    print("🔄 La transcription continue en arrière-plan...")
                    print(f"📊 Vérifiez le statut manuellement: {API_BASE}/transcription-status/{task_id}")
                    return False
                    
            else:
                print(f"❌ Erreur lors de la vérification: {response.status_code}")
                if response.status_code == 404:
                    print("❌ Task ID non trouvé - la transcription a peut-être échoué")
                    return False
                    
        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            # Continuer malgré l'erreur temporaire
        
        # Attendre 30 secondes avant la prochaine vérification
        time.sleep(30)

def main():
    """Fonction principale"""
    print("🧪 Test de transcription longue - La Boîte de Chocolat")
    print("=" * 60)
    
    # Test de santé
    if not test_health():
        print("❌ Service non disponible, arrêt du test")
        sys.exit(1)
    
    # Démarrer la transcription
    task_id = test_async_transcription()
    if not task_id:
        print("❌ Impossible de démarrer la transcription")
        sys.exit(1)
    
    # Surveiller la progression
    success = monitor_transcription(task_id, max_hours=6)
    
    if success:
        print("\n🎉 Test réussi! La transcription longue fonctionne correctement.")
    else:
        print("\n⚠️  Test terminé. Vérifiez manuellement le statut de la transcription.")
    
    print(f"\n📊 Pour vérifier le statut: {API_BASE}/transcription-status/{task_id}")
    print(f"📋 Pour lister toutes les tâches: {API_BASE}/tasks")

if __name__ == "__main__":
    main() 