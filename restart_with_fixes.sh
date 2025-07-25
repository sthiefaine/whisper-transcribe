#!/bin/bash

echo "🔧 Redémarrage du service avec corrections pour transcriptions longues"
echo "=" * 60

# Arrêter les services
echo "🛑 Arrêt des services..."
docker-compose down

# Nettoyer les conteneurs pour forcer la reconstruction
echo "🧹 Nettoyage des conteneurs..."
docker-compose rm -f

# Reconstruire avec les nouvelles configurations
echo "🔨 Reconstruction des images..."
docker-compose build --no-cache

# Redémarrer les services
echo "🚀 Redémarrage des services..."
docker-compose up -d

# Attendre le démarrage
echo "⏳ Attente du démarrage (30 secondes)..."
sleep 30

# Vérifier la santé
echo "🏥 Vérification de la santé du service..."
for i in {1..10}; do
    if curl -f http://localhost:8090/health > /dev/null 2>&1; then
        echo "✅ Service démarré avec succès!"
        echo ""
        echo "📡 API disponible sur: http://localhost:8090"
        echo "🔍 Health check: http://localhost:8090/health"
        echo "📋 Modèles: http://localhost:8090/models"
        echo ""
        echo "🧪 Pour tester les transcriptions longues:"
        echo "   python3 test_long_transcription.py"
        echo ""
        echo "📊 Pour voir les logs:"
        echo "   docker-compose logs -f whisper-api"
        echo ""
        echo "🛑 Pour arrêter:"
        echo "   docker-compose down"
        exit 0
    else
        echo "⏳ Tentative $i/10 - Service en cours de démarrage..."
        sleep 10
    fi
done

echo "❌ Le service ne répond pas après 10 tentatives"
echo "📊 Logs:"
docker-compose logs whisper-api
exit 1 