# 🐳 Guide Docker Mac - Whisper Transcription

## 🚀 Démarrage simple

### 1. Vérifier Docker
```bash
# Vérifier que Docker Desktop est installé et démarré
docker --version
docker info
```

### 2. Lancer le service
```bash
# Rendre les scripts exécutables
chmod +x run_local_mac.sh manage_local.sh

# Démarrer le service (crée l'image + lance le container)
./manage_local.sh start
```

### 3. Vérifier que ça fonctionne
```bash
# Vérifier le statut
./manage_local.sh status

# Tester l'API
curl http://localhost:8080/health
```

## 🔧 Commandes Docker manuelles

### Construire l'image
```bash
# Construire l'image depuis le Dockerfile
docker build -t whisper-api .

# Voir les images créées
docker images
```

### Lancer le container
```bash
# Lancer le container depuis l'image
docker run -d \
  --name whisper-api \
  -p 8080:8080 \
  -v whisper-models:/opt/whisper.cpp/models \
  -v ./logs:/var/log/whisper \
  whisper-api

# Voir les containers en cours
docker ps
```

### Gérer le container
```bash
# Arrêter le container
docker stop whisper-api

# Redémarrer le container
docker start whisper-api

# Supprimer le container
docker rm whisper-api

# Voir les logs
docker logs whisper-api

# Voir les logs en temps réel
docker logs -f whisper-api
```

## 📋 Commandes utiles

### Lister les images
```bash
docker images
```

### Lister les containers
```bash
# Containers en cours
docker ps

# Tous les containers (même arrêtés)
docker ps -a
```

### Nettoyer
```bash
# Supprimer les containers arrêtés
docker container prune

# Supprimer les images non utilisées
docker image prune

# Nettoyer tout
docker system prune
```

## 🧪 Test rapide

### 1. Démarrer
```bash
./manage_local.sh start
```

### 2. Tester
```bash
# Test de santé
curl http://localhost:8080/health

# Test de transcription
curl -X POST -H "Content-Type: application/json" \
  -d '{
    "audio_url": "https://example.com/audio.mp3",
    "model": "large-v3",
    "language": "fr"
  }' \
  http://localhost:8080/transcribe-async
```

### 3. Surveiller
```bash
# Voir les logs
./manage_local.sh logs

# Voir les ressources
docker stats whisper-api
```

## 🛠️ Dépannage

### Container ne démarre pas
```bash
# Voir les logs d'erreur
docker logs whisper-api

# Vérifier l'espace disque
df -h

# Vérifier la mémoire Docker
docker system df
```

### Port déjà utilisé
```bash
# Voir qui utilise le port 8080
lsof -i :8080

# Changer le port dans docker-compose.local.yml
# ports:
#   - "8081:8080"  # Port 8081 au lieu de 8080
```

### Problème de permissions
```bash
# Donner les bonnes permissions
chmod +x *.sh
chmod 755 logs/
```

## 📊 Monitoring

### Ressources utilisées
```bash
# Voir l'utilisation CPU/mémoire
docker stats

# Voir les détails du container
docker inspect whisper-api
```

### Logs détaillés
```bash
# Logs avec timestamps
docker logs -t whisper-api

# Logs des dernières 100 lignes
docker logs --tail 100 whisper-api

# Logs depuis une date
docker logs --since "2025-07-25T10:00:00" whisper-api
```

## 🎯 Workflow recommandé

1. **Développement** : `./manage_local.sh start`
2. **Test** : `curl http://localhost:8080/health`
3. **Utilisation** : `curl -X POST ... /transcribe-async`
4. **Surveillance** : `./manage_local.sh logs`
5. **Arrêt** : `./manage_local.sh stop` 