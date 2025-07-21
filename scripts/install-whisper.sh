#!/bin/bash

echo "🚀 Installation de Whisper.cpp..."

# Vérifier les dépendances
if ! command -v git &> /dev/null; then
    echo "❌ Git non trouvé"
    exit 1
fi

if ! command -v make &> /dev/null; then
    echo "❌ Make non trouvé"
    exit 1
fi

# Cloner et compiler Whisper.cpp
cd /opt
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
make

echo "✅ Whisper.cpp installé avec succès" 