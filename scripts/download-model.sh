#!/bin/bash
set -e

MODEL=${1:-large}
MODEL_FILE="ggml-${MODEL}.bin"
MODEL_PATH="./models/${MODEL_FILE}"

if [ ! -f "$MODEL_PATH" ]; then
  echo "Téléchargement du modèle $MODEL..."
  wget -O "$MODEL_PATH" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${MODEL_FILE}"
else
  echo "Le modèle $MODEL existe déjà : $MODEL_PATH"
fi 