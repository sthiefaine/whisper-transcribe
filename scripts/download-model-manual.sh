#!/bin/bash

echo "📥 Téléchargement manuel du modèle Whisper base..."

# Créer le dossier models s'il n'existe pas
mkdir -p models

# URL du modèle base
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
MODEL_FILE="models/ggml-base.bin"

echo "🔗 Téléchargement depuis: $MODEL_URL"
echo "📁 Sauvegarde dans: $MODEL_FILE"

# Télécharger avec wget ou curl
if command -v wget &> /dev/null; then
    wget -O "$MODEL_FILE" "$MODEL_URL"
elif command -v curl &> /dev/null; then
    curl -L -o "$MODEL_FILE" "$MODEL_URL"
else
    echo "❌ Ni wget ni curl ne sont installés"
    exit 1
fi

# Vérifier le téléchargement
if [ -f "$MODEL_FILE" ]; then
    size=$(ls -lh "$MODEL_FILE" | awk '{print $5}')
    echo "✅ Modèle téléchargé avec succès: $size"
else
    echo "❌ Échec du téléchargement"
    exit 1
fi 