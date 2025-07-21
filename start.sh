#!/bin/bash

echo "🚀 Démarrage du service Whisper - La Boîte de Chocolat"
echo "=" * 50

# Vérifier que Docker est installé
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé"
    echo "💡 Installez Docker depuis: https://docs.docker.com/get-docker/"
    exit 1
fi

# Vérifier que Docker Compose est installé
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose n'est pas installé"
    echo "💡 Installez Docker Compose depuis: https://docs.docker.com/compose/install/"
    exit 1
fi

# Vérifier que le fichier de test existe
if [ ! -f "data/avatar_test_short.mp3" ]; then
    echo "⚠️  Fichier de test non trouvé: data/avatar_test_short.mp3"
    echo "💡 Assurez-vous d'avoir le fichier de test audio"
fi

echo "🔧 Construction de l'image Docker..."
docker-compose build

echo "🚀 Démarrage des services..."
docker-compose up -d

echo "⏳ Attente du démarrage du service..."
sleep 10

echo "🏥 Vérification de la santé du service..."
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Service démarré avec succès!"
    echo ""
    echo "📡 API disponible sur: http://localhost:8080"
    echo "🔍 Health check: http://localhost:8080/health"
    echo "📋 Modèles: http://localhost:8080/models"
    echo ""
    echo "🧪 Pour tester avec le fichier audio:"
    echo "   python3 test_local.py"
    echo ""
    echo "📊 Pour voir les logs:"
    echo "   docker-compose logs -f whisper-api"
    echo ""
    echo "🛑 Pour arrêter:"
    echo "   docker-compose down"
else
    echo "❌ Le service ne répond pas"
    echo "📊 Logs:"
    docker-compose logs whisper-api
fi 