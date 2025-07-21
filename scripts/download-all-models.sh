#!/bin/bash

set -e

cd /opt/whisper.cpp || exit 1

for model in tiny base small medium large large-v2; do
  echo "Téléchargement du modèle $model..."
  bash ./models/download-ggml-model.sh $model
  echo "✅ Modèle $model téléchargé."
done

echo "🎉 Tous les modèles ont été téléchargés avec succès !" 