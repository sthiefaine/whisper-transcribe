#!/bin/bash

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <model-name>"
    echo "Exemples :"
    echo "  $0 base"
    echo "  $0 large-v3"
    echo "  $0 large-v3-turbo-q8_0"
    exit 1
fi

MODEL=$1
MODEL_DIR="$(dirname "$0")"
MODEL_FILE="ggml-${MODEL}.bin"
MODEL_PATH="${MODEL_DIR}/${MODEL_FILE}"
BASE_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main"

# Si le fichier existe déjà, on ne télécharge pas
if [ -f "${MODEL_PATH}" ]; then
    echo "✅ Modèle déjà téléchargé : ${MODEL_PATH}"
    exit 0
fi

echo "⬇️ Téléchargement du modèle : ${MODEL_FILE}..."
curl -L -o "${MODEL_PATH}" "${BASE_URL}/${MODEL_FILE}"

if [ $? -eq 0 ]; then
    echo "✅ Téléchargement réussi : ${MODEL_FILE}"
else
    echo "❌ Échec du téléchargement : ${MODEL_FILE}"
    exit 1
fi
