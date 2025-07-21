#!/usr/bin/env python3
"""
Test simple du service Whisper en local
"""

import requests
import os
import time

def test_local_transcription():
    """Test de transcription avec le fichier local"""
    
    # Vérifier que le fichier existe
    test_file = "data/avatar_test_short.mp3"
    if not os.path.exists(test_file):
        print(f"❌ Fichier de test non trouvé: {test_file}")
        return False
    
    print(f"🎤 Test de transcription avec: {test_file}")
    print(f"📊 Taille du fichier: {os.path.getsize(test_file) / (1024*1024):.1f} MB")
    
    # Préparer la requête
    url = "http://localhost:8080/transcribe/file"
    
    with open(test_file, 'rb') as audio_file:
        files = {'audio_file': audio_file}
        data = {
            'language': 'fr',
            'model': 'base'
        }
        
        print("🚀 Envoi de la requête...")
        start_time = time.time()
        
        try:
            response = requests.post(
                url,
                files=files,
                data=data,
                timeout=600  # 10 minutes
            )
            
            total_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Transcription réussie!")
                print(f"⏱️  Temps total: {total_time:.2f}s")
                print(f"⚡ Temps de traitement: {result.get('processing_time', 0):.2f}s")
                print(f"📝 Transcription: {result.get('transcription', '')[:200]}...")
                return True
            else:
                print(f"❌ Erreur: {response.status_code}")
                print(f"📄 Réponse: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            print("⏰ Timeout - Le service prend trop de temps")
            return False
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False

if __name__ == "__main__":
    print("🧪 Test local du service Whisper")
    print("=" * 50)
    
    success = test_local_transcription()
    
    if success:
        print("\n🎉 Test réussi ! Le service fonctionne correctement.")
    else:
        print("\n⚠️  Test échoué. Vérifiez que le service est démarré.")
        print("💡 Pour démarrer le service: python3 server.py") 