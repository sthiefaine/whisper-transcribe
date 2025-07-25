#!/bin/bash

echo "🔍 Diagnostic spécifique Coolify - Pourquoi le processus est tué après 2h"
echo "=" * 70

echo "📊 1. Vérification des limites de ressources Coolify..."
echo "   - Mémoire allouée: $(docker inspect whisper-api 2>/dev/null | jq -r '.[0].HostConfig.Memory // "Non défini"')"
echo "   - CPU alloué: $(docker inspect whisper-api 2>/dev/null | jq -r '.[0].HostConfig.CpuQuota // "Non défini"')"

echo ""
echo "📊 2. Vérification des timeouts Coolify..."
echo "   - Stop grace period: $(docker inspect whisper-api 2>/dev/null | jq -r '.[0].Config.StopGracePeriod // "Non défini"')"
echo "   - Health check interval: $(docker inspect whisper-api 2>/dev/null | jq -r '.[0].Config.Healthcheck.Interval // "Non défini"')"

echo ""
echo "📊 3. Logs système pour détecter les kills..."
echo "   Recherche des messages de kill dans les logs système:"
journalctl --since "1 hour ago" | grep -i "killed\|oom\|memory\|whisper" | tail -20

echo ""
echo "📊 4. Vérification des processus zombies..."
ps aux | grep -i "defunct\|zombie" | grep -v grep

echo ""
echo "📊 5. Vérification de l'utilisation mémoire..."
free -h
echo ""
docker stats --no-stream whisper-api 2>/dev/null || echo "Stats non disponibles"

echo ""
echo "📊 6. Vérification des limites système..."
echo "   - ulimit -a:"
ulimit -a

echo ""
echo "📊 7. Vérification des cgroups..."
if [ -d "/sys/fs/cgroup/memory" ]; then
    echo "   Limites mémoire cgroup:"
    cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null | numfmt --to=iec || echo "Non accessible"
fi

echo ""
echo "📊 8. Vérification des logs Docker..."
echo "   Derniers logs Docker avec timestamps:"
docker logs --timestamps --tail=20 whisper-api 2>/dev/null | grep -E "(error|killed|oom|timeout)" || echo "Aucune erreur trouvée"

echo ""
echo "🔧 9. Recommandations pour Coolify:"
echo "   - Vérifiez les paramètres de timeout dans l'interface Coolify"
echo "   - Augmentez les limites de mémoire et CPU"
echo "   - Désactivez les health checks agressifs"
echo "   - Configurez des timeouts plus longs pour les processus"

echo ""
echo "📋 10. Commandes pour forcer les limites:"
echo "   # Dans l'interface Coolify, configurez:"
echo "   - Memory: 16GB minimum"
echo "   - CPU: 4 cores minimum"
echo "   - Process timeout: 86400s (24h)"
echo "   - Health check: interval 60s, timeout 30s, retries 5" 