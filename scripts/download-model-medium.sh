#!/bin/bash

echo "📥 Téléchargement du modèle Whisper medium..."

# Créer le dossier models s'il n'existe pas
mkdir -p models

# URL du modèle medium
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin"
MODEL_FILE="models/ggml-medium.bin"

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
    echo "✅ Modèle medium téléchargé avec succès: $size"
else
    echo "❌ Échec du téléchargement"
    exit 1
fi 