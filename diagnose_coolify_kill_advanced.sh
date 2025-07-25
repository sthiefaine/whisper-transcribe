#!/bin/bash

echo "🔍 Diagnostic avancé Coolify - Identification précise du kill"
echo "=" * 70

echo "📊 1. Vérification des processus système..."
echo "   Processus avec PID élevé (potentiellement Whisper):"
ps aux | grep -E "(whisper|python)" | grep -v grep

echo ""
echo "📊 2. Vérification des logs système pour les kills..."
echo "   Recherche des messages de kill dans les 2 dernières heures:"
journalctl --since "2 hours ago" | grep -i "killed\|oom\|memory\|whisper\|python" | tail -20

echo ""
echo "📊 3. Vérification des cgroups et limites..."
echo "   Limites mémoire système:"
cat /proc/meminfo | grep -E "(MemTotal|MemAvailable|MemFree)"

echo ""
echo "📊 4. Vérification des conteneurs Docker..."
echo "   Statut des conteneurs:"
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Size}}"

echo ""
echo "📊 5. Vérification des logs Docker détaillés..."
echo "   Derniers logs avec timestamps:"
docker logs --timestamps --tail=50 whisper-api 2>/dev/null | grep -E "(error|killed|oom|timeout|signal)" || echo "Aucune erreur trouvée"

echo ""
echo "📊 6. Vérification des ressources utilisées..."
echo "   Utilisation mémoire et CPU:"
docker stats --no-stream whisper-api 2>/dev/null || echo "Stats non disponibles"

echo ""
echo "📊 7. Vérification des timeouts Coolify..."
echo "   Configuration actuelle:"
docker inspect whisper-api 2>/dev/null | jq -r '.[0].Config.Env[] | select(test("COOLIFY|TIMEOUT"))' || echo "Aucune config timeout trouvée"

echo ""
echo "📊 8. Vérification des signaux reçus..."
echo "   Recherche de signaux dans les logs:"
docker logs whisper-api 2>/dev/null | grep -i "signal\|sigterm\|sigkill" | tail -10 || echo "Aucun signal trouvé"

echo ""
echo "📊 9. Vérification des health checks..."
echo "   État des health checks:"
docker inspect whisper-api 2>/dev/null | jq -r '.[0].State.Health' || echo "Health check non configuré"

echo ""
echo "📊 10. Vérification des limites de ressources..."
echo "   Limites imposées par Docker:"
docker inspect whisper-api 2>/dev/null | jq -r '.[0].HostConfig | {Memory: .Memory, CpuQuota: .CpuQuota, CpuPeriod: .CpuPeriod}' || echo "Limites non trouvées"

echo ""
echo "🔧 11. Recommandations immédiates:"
echo "   - Vérifiez l'interface Coolify pour les timeouts"
echo "   - Augmentez les limites de mémoire à 20GB minimum"
echo "   - Désactivez les health checks agressifs"
echo "   - Configurez un timeout de processus à 24h"
echo "   - Vérifiez les logs Coolify pour les timeouts automatiques"

echo ""
echo "📋 12. Commandes pour forcer les limites:"
echo "   # Dans l'interface Coolify:"
echo "   - Memory: 20GB"
echo "   - CPU: 6 cores"
echo "   - Process timeout: 86400s"
echo "   - Health check: interval 120s, timeout 60s, retries 10"
echo "   - Désactiver les timeouts automatiques"

echo ""
echo "📊 13. Test de résistance..."
echo "   Pour tester si le problème vient de Coolify:"
echo "   docker run --rm -it --memory=20g --cpus=6.0 -v /var/run/docker.sock:/var/run/docker.sock ubuntu:22.04 bash -c 'sleep 7200'" 