#!/bin/bash

echo "🍎 Démarrage du service Whisper sur Docker local (MacBook)"
echo "=" * 60

# Vérifier que Docker est installé
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé"
    echo "💡 Installez Docker Desktop depuis: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Vérifier que Docker Desktop est démarré
if ! docker info &> /dev/null; then
    echo "❌ Docker Desktop n'est pas démarré"
    echo "💡 Démarrez Docker Desktop et réessayez"
    exit 1
fi

echo "✅ Docker est disponible"

# Créer le dossier models s'il n'existe pas
mkdir -p models

# Télécharger le modèle large-v3 s'il n'existe pas
if [ ! -f "models/ggml-large-v3.bin" ]; then
    echo "📥 Téléchargement du modèle large-v3..."
    chmod +x download_models.sh
    ./download_models.sh large-v3
else
    echo "✅ Modèle large-v3 déjà présent"
fi

# Créer un docker-compose.local.yml optimisé pour MacBook
echo "📝 Création de la configuration Docker pour MacBook..."

cat > docker-compose.local.yml << 'EOF'
version: '3.8'

services:
  whisper-api:
    build: .
    ports:
      - "8080:8080"  # Port direct sans nginx
    environment:
      - FLASK_ENV=development
      - PYTHONUNBUFFERED=1
      - PYTHONHASHSEED=random
      - PYTHONDONTWRITEBYTECODE=1
    volumes:
      - ./models:/opt/whisper.cpp/models  # Monter les modèles locaux
      - ./logs:/var/log/whisper
      - ./data:/data  # Pour les fichiers de test
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 8G   # Limite adaptée pour MacBook
          cpus: '4.0'  # 4 cores
        reservations:
          memory: 4G
          cpus: '2.0'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # Nginx optionnel pour le local
  nginx:
    build:
      context: ./nginx
      dockerfile: Dockerfile
    ports:
      - "8090:80"  # Port différent pour éviter conflits
    depends_on:
      - whisper-api
    restart: unless-stopped 
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    profiles:
      - nginx  # Optionnel, pas démarré par défaut

volumes:
  whisper-models:
EOF

echo "✅ Configuration Docker créée"

# Arrêter les services existants
echo "🛑 Arrêt des services existants..."
docker-compose -f docker-compose.local.yml down 2>/dev/null || true

# Nettoyer les conteneurs
echo "🧹 Nettoyage des conteneurs..."
docker-compose -f docker-compose.local.yml rm -f 2>/dev/null || true

# Construire l'image
echo "🔨 Construction de l'image Docker..."
docker-compose -f docker-compose.local.yml build --no-cache

# Démarrer le service principal (sans nginx)
echo "🚀 Démarrage du service Whisper..."
docker-compose -f docker-compose.local.yml up -d whisper-api

echo ""
echo "✅ Service démarré!"
echo ""
echo "📡 API disponible sur: http://localhost:8080"
echo "🔍 Health check: http://localhost:8080/health"
echo "📋 Modèles: http://localhost:8080/models"
echo ""
echo "📊 Pour voir les logs:"
echo "   docker-compose -f docker-compose.local.yml logs -f whisper-api"
echo ""
echo "🛑 Pour arrêter:"
echo "   docker-compose -f docker-compose.local.yml down"
echo ""
echo "🌐 Pour démarrer avec nginx (optionnel):"
echo "   docker-compose -f docker-compose.local.yml --profile nginx up -d"
echo "   # Puis accéder via http://localhost:8090" 