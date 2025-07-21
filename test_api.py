#!/usr/bin/env python3
"""
Script de test pour l'API Whisper
"""

import requests
import json
import time

# Configuration
API_BASE_URL = "http://localhost:8080"

def test_health():
    """Test du health check"""
    print("🏥 Test du health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check OK: {data}")
            return True
        else:
            print(f"❌ Health check échoué: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur health check: {e}")
        return False

def test_models():
    """Test de l'endpoint models"""
    print("📋 Test de l'endpoint models...")
    try:
        response = requests.get(f"{API_BASE_URL}/models", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Models OK: {data}")
            return True
        else:
            print(f"❌ Models échoué: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur models: {e}")
        return False

def test_transcription():
    """Test de transcription avec un fichier audio de test"""
    print("🎤 Test de transcription...")
    
    # Utiliser le fichier local de test
    test_audio_path = "data/avatar_test_short.mp3"
    
    # Vérifier que le fichier existe
    import os
    if not os.path.exists(test_audio_path):
        print(f"❌ Fichier de test non trouvé: {test_audio_path}")
        return False
    
    print(f"📁 Utilisation du fichier local: {test_audio_path}")
    
    payload = {
        "audio_file": test_audio_path,  # Utiliser le chemin local
        "language": "fr",  # Le fichier est probablement en français
        "model": "base"
    }
    
    try:
        print(f"📥 Transcription du fichier local: {test_audio_path}")
        start_time = time.time()
        
        # Pour les fichiers locaux, nous devons les envoyer comme multipart/form-data
        with open(test_audio_path, 'rb') as audio_file:
            files = {'audio_file': audio_file}
            data = {
                'language': payload['language'],
                'model': payload['model']
            }
            
            response = requests.post(
                f"{API_BASE_URL}/transcribe/file",
                files=files,
                data=data,
                timeout=300  # 5 minutes pour un fichier de 145MB
            )
        
        processing_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Transcription réussie en {processing_time:.2f}s")
            print(f"📝 Texte: {data.get('transcription', 'Aucun texte')}")
            print(f"⚡ Temps de traitement: {data.get('processing_time', 0):.2f}s")
            return True
        else:
            print(f"❌ Transcription échouée: {response.status_code}")
            print(f"📄 Réponse: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur transcription: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🧪 Tests de l'API Whisper")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health),
        ("List Models", test_models),
        ("Transcription", test_transcription)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        print("-" * 30)
        success = test_func()
        results.append((test_name, success))
        time.sleep(1)  # Pause entre les tests
    
    # Résumé
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 50)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 {passed}/{len(results)} tests réussis")
    
    if passed == len(results):
        print("🎉 Tous les tests sont passés ! L'API fonctionne correctement.")
    else:
        print("⚠️  Certains tests ont échoué. Vérifiez la configuration.")

if __name__ == "__main__":
    main() 