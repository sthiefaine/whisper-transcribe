#!/bin/bash

echo "🔍 Vérification de la configuration nginx après démarrage"
echo "=" * 50

echo "⏳ Attente que les services soient prêts..."
sleep 10

echo "📊 Test de la configuration nginx dans le conteneur..."
docker-compose exec nginx nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Configuration nginx valide"
else
    echo "❌ Erreur dans la configuration nginx"
    echo "📄 Logs nginx:"
    docker-compose logs nginx
    exit 1
fi

echo ""
echo "📊 Test de la connectivité entre nginx et whisper-api..."
docker-compose exec nginx ping -c 3 whisper-api

echo ""
echo "📊 Test de l'endpoint health via nginx..."
curl -f http://localhost:8090/health

if [ $? -eq 0 ]; then
    echo "✅ Service accessible via nginx"
else
    echo "❌ Service non accessible via nginx"
    echo "📄 Logs nginx:"
    docker-compose logs nginx
    echo "📄 Logs whisper:"
    docker-compose logs whisper-api
    exit 1
fi

echo ""
echo "🎉 Configuration nginx validée avec succès!" 