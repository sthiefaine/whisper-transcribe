#!/bin/bash

echo "📥 Téléchargement des modèles..."

cd /opt/whisper.cpp

# Modèle français (base)
bash ./models/download-ggml-model.sh base

# Modèle français (small) - optionnel
# bash ./models/download-ggml-model.sh small

echo "✅ Modèles téléchargés" 