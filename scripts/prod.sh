#!/bin/bash

echo "🚀 Redémarrage en Mode Production - Whisper Service"
echo "=================================================="
echo ""

# Arrêter les services
echo "🛑 Arrêt des services..."
docker-compose down

# Nettoyer les images pour forcer le rebuild
echo "🧹 Nettoyage des images..."
docker system prune -f

# Reconstruire avec les nouvelles configurations
echo "🔨 Reconstruction des images..."
docker-compose build --no-cache

# Démarrer en mode production
echo "🚀 Démarrage en mode production..."
docker-compose up -d

# Attendre le démarrage
echo "⏳ Attente du démarrage..."
sleep 15

# Vérifier la santé
echo "🏥 Vérification de la santé..."
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Service démarré en mode production!"
    echo ""
    echo "📡 API disponible sur: http://localhost:8080"
    echo "🔍 Health check: http://localhost:8080/health"
    echo "📋 Modèles: http://localhost:8080/models"
    echo ""
    echo "📊 Logs de production:"
    echo "   docker-compose logs -f whisper-api"
    echo ""
    echo "🛑 Pour arrêter:"
    echo "   docker-compose down"
else
    echo "❌ Le service ne répond pas"
    echo "📊 Logs:"
    docker-compose logs whisper-api
fi 