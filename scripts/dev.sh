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

# Vérifier si Whisper.cpp est installé (Docker ou Local)
if [ -d "/opt/whisper.cpp" ]; then
    echo "🐳 Whisper.cpp détecté en mode Docker"
    WHISPER_PATH="/opt/whisper.cpp"
elif [ -d "$HOME/whisper.cpp" ]; then
    echo "💻 Whisper.cpp détecté en mode Local"
    WHISPER_PATH="$HOME/whisper.cpp"
else
    echo "⚠️  Whisper.cpp n'est pas installé"
    echo "💡 Pour l'installer en local:"
    echo "   cd ~ && git clone https://github.com/ggerganov/whisper.cpp.git"
    echo "   cd whisper.cpp && make"
    echo "   bash ./models/download-ggml-model.sh large-v3"
    echo ""
    echo "🔗 Ou utilisez Docker: npm start"
    exit 1
fi

# Vérifier si le modèle est téléchargé
if [ ! -f "$WHISPER_PATH/models/ggml-base.bin" ]; then
    echo "⚠️  Modèle base non trouvé"
    echo "💡 Pour le télécharger:"
    echo "   cd $WHISPER_PATH && bash ./models/download-ggml-model.sh base"
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

# Démarrer le serveur (détection automatique Docker/Local)
python3 server.py 