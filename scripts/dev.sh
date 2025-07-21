#!/bin/bash

echo "🔧 Mode Développement - Whisper Service"
echo "======================================"
echo ""

# Vérifier que Python est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 n'est pas installé"
    exit 1
fi

# Vérifier que pip est installé
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 n'est pas installé"
    exit 1
fi

echo "📦 Installation des dépendances Python..."
pip3 install -r requirements.txt

echo ""
echo "🔍 Vérification de Whisper.cpp..."

# Vérifier si Whisper.cpp est installé
if [ ! -d "/opt/whisper.cpp" ]; then
    echo "⚠️  Whisper.cpp n'est pas installé dans /opt/whisper.cpp"
    echo "💡 Pour l'installer:"
    echo "   sudo ./scripts/install-whisper.sh"
    echo ""
    echo "🔗 Ou utilisez Docker: npm start"
    exit 1
fi

# Vérifier si le modèle est téléchargé
if [ ! -f "/opt/whisper.cpp/models/ggml-base.bin" ]; then
    echo "⚠️  Modèle base non trouvé"
    echo "💡 Pour le télécharger:"
    echo "   sudo ./scripts/download-models.sh"
    echo ""
    echo "🔗 Ou utilisez Docker: npm start"
    exit 1
fi

echo "✅ Whisper.cpp et modèle détectés"
echo ""

echo "🚀 Démarrage du serveur de développement..."
echo "📡 API disponible sur: http://localhost:8080"
echo "🛑 Pour arrêter: Ctrl+C"
echo ""

# Démarrer le serveur
python3 server.py 