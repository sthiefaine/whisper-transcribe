#!/bin/bash

echo "🚀 Démarrage Whisper Service - Mode Local macOS"
echo "=============================================="
echo ""

# Vérifier que Whisper.cpp est installé
if [ ! -d "$HOME/whisper.cpp" ]; then
    echo "❌ Whisper.cpp non trouvé dans ~/whisper.cpp"
    echo "💡 Installez-le avec:"
    echo "   cd ~ && git clone https://github.com/ggerganov/whisper.cpp.git"
    echo "   cd whisper.cpp && make"
    echo "   bash ./models/download-ggml-model.sh large-v3"
    exit 1
fi

# Vérifier que le modèle large-v3 est téléchargé
if [ ! -f "$HOME/whisper.cpp/models/ggml-large-v3.bin" ]; then
    echo "⚠️  Modèle large-v3 non trouvé"
    echo "💡 Téléchargez-le avec:"
    echo "   cd ~/whisper.cpp && bash ./models/download-ggml-model.sh large-v3"
    exit 1
fi

echo "✅ Whisper.cpp et modèle large-v3 détectés"
echo ""

# Installer les dépendances Python si nécessaire
echo "📦 Vérification des dépendances Python..."
pip3 install -r requirements.txt

echo ""
echo "🚀 Démarrage du serveur local..."
echo "📡 API disponible sur: http://localhost:8080"
echo "🔍 Health check: http://localhost:8080/health"
echo "📋 Modèles: http://localhost:8080/models"
echo ""
echo "🛑 Pour arrêter: Ctrl+C"
echo ""

# Démarrer le serveur (détection automatique Docker/Local)
python3 server.py 