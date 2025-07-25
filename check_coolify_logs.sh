#!/bin/bash

echo "🔍 Diagnostic des logs Coolify pour identifier l'arrêt silencieux"
echo "=" * 60

echo "📊 Logs du conteneur Whisper:"
docker-compose logs --tail=50 whisper-api

echo ""
echo "📊 Logs Nginx:"
docker-compose logs --tail=20 nginx

echo ""
echo "📊 Logs système (dernières 100 lignes):"
docker exec whisper-api cat /var/log/syslog 2>/dev/null | tail -50 || echo "Logs système non disponibles"

echo ""
echo "📊 Vérification des processus dans le conteneur:"
docker exec whisper-api ps aux 2>/dev/null || echo "Impossible d'accéder aux processus"

echo ""
echo "📊 Utilisation mémoire du conteneur:"
docker stats --no-stream whisper-api 2>/dev/null || echo "Stats non disponibles"

echo ""
echo "🔍 Recherche d'erreurs OOM (Out of Memory):"
docker exec whisper-api dmesg 2>/dev/null | grep -i "killed\|oom\|memory" | tail -10 || echo "Aucune erreur OOM trouvée" 