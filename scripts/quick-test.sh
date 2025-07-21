#!/bin/bash

echo "⚡ Test Rapide - Whisper Service"
echo "==============================="
echo ""

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction pour afficher les résultats
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

# Test 1: Vérifier que le service répond
echo "🔍 Test 1: Health Check"
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    print_result 0 "Service accessible"
else
    print_result 1 "Service non accessible"
    echo "💡 Démarrez le service: npm start"
    exit 1
fi

# Test 2: Vérifier les modèles
echo ""
echo "🔍 Test 2: Modèles disponibles"
if curl -s http://localhost:8080/models | grep -q "ggml-base.bin"; then
    print_result 0 "Modèle base disponible"
else
    print_result 1 "Modèle base non trouvé"
fi

# Test 3: Vérifier le fichier de test
echo ""
echo "🔍 Test 3: Fichier de test"
if [ -f "data/avatar_test_short.mp3" ]; then
    size=$(ls -lh data/avatar_test_short.mp3 | awk '{print $5}')
    print_result 0 "Fichier de test trouvé ($size)"
else
    print_result 1 "Fichier de test non trouvé"
    echo "💡 Placez votre fichier audio dans data/avatar_test_short.mp3"
fi

# Test 4: Test de transcription rapide (si fichier < 10MB)
echo ""
echo "🔍 Test 4: Test de transcription"
if [ -f "data/avatar_test_short.mp3" ]; then
    file_size=$(stat -f%z data/avatar_test_short.mp3 2>/dev/null || stat -c%s data/avatar_test_short.mp3 2>/dev/null)
    if [ $file_size -lt 10485760 ]; then  # 10MB
        echo "📤 Test de transcription en cours..."
        start_time=$(date +%s)
        
        response=$(curl -s -X POST http://localhost:8080/transcribe/file \
            -F "audio_file=@data/avatar_test_short.mp3" \
            -F "language=fr" \
            -F "model=base" \
            --max-time 60)
        
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        
        if echo "$response" | grep -q "success.*true"; then
            print_result 0 "Transcription réussie (${duration}s)"
            transcription=$(echo "$response" | grep -o '"transcription":"[^"]*"' | cut -d'"' -f4)
            echo "📝 Extrait: ${transcription:0:100}..."
        else
            print_result 1 "Transcription échouée"
            echo "📄 Erreur: $response"
        fi
    else
        echo -e "${YELLOW}⚠️  Fichier trop volumineux pour test rapide (>10MB)${NC}"
        echo "💡 Utilisez: npm run test-local pour un test complet"
    fi
else
    print_result 1 "Pas de fichier de test"
fi

echo ""
echo "🎯 RÉSUMÉ"
echo "=========="
echo "📡 API: http://localhost:8080"
echo "🔍 Health: http://localhost:8080/health"
echo "📋 Modèles: http://localhost:8080/models"
echo ""
echo "💡 Commandes utiles:"
echo "   npm run logs      - Voir les logs"
echo "   npm run test-local - Test complet"
echo "   npm run help      - Tous les scripts" 