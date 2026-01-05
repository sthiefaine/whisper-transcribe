# Scriberr - Service de Transcription Audio

Service de transcription audio moderne utilisant Scriberr (WhisperX optimisé) pour gérer les longs podcasts sans problème. Optimisé pour les serveurs Linux/Hetzner avec Coolify.

## 🚀 Fonctionnalités

- ✅ Transcription de longs podcasts (optimisé WhisperX)
- ✅ Diarisation (identification des locuteurs) avec HuggingFace
- ✅ Interface web moderne
- ✅ API REST complète
- ✅ Support GPU NVIDIA (optionnel)
- ✅ Déploiement Docker Compose simple
- ✅ Prêt pour Coolify/Hetzner

## 📋 Prérequis

- Docker et Docker Compose installés
- Serveur Linux (Ubuntu/Debian recommandé)
- Optionnel : Token HuggingFace pour la diarisation (gratuit)

## 🔧 Installation Rapide

### Étape 1 : Préparation du serveur

```bash
# Vérifier Docker
docker --version
docker-compose --version

# Cloner ou naviguer vers le projet
cd ~/scriberr  # ou votre répertoire
```

### Étape 2 : Configuration

1. **Copier le fichier d'environnement :**
```bash
cp .env.example .env
```

2. **Éditer `.env` et ajouter votre token HuggingFace (optionnel mais recommandé) :**
```bash
nano .env
```

Obtenez votre token gratuit sur [HuggingFace Settings](https://huggingface.co/settings/tokens)

### Étape 3 : Déploiement

```bash
# Rendre le script exécutable (si pas déjà fait)
chmod +x deploy.sh

# Démarrer Scriberr
./deploy.sh up
```

### Étape 4 : Accès

Accédez à l'interface web :
- **Local** : http://localhost:8080
- **Serveur distant** : http://VOTRE_IP:8080

## 📖 Utilisation

### Interface Web

1. Ouvrez http://VOTRE_IP:8080 dans votre navigateur
2. Uploadez votre fichier audio (MP3, WAV, M4A, etc.)
3. Configurez les options (langue, diarisation, etc.)
4. Lancez la transcription
5. Téléchargez le résultat (TXT, SRT, VTT)

### API REST

#### Transcription simple

```bash
curl -X POST http://VOTRE_IP:8080/api/transcribe \
  -H "Content-Type: multipart/form-data" \
  -F "file=@votre_audio.mp3" \
  -F "language=fr" \
  -F "diarize=true"
```

#### Transcription avec diarisation

```bash
curl -X POST http://VOTRE_IP:8080/api/transcribe \
  -H "Content-Type: multipart/form-data" \
  -F "file=@podcast.mp3" \
  -F "language=fr" \
  -F "diarize=true" \
  -F "num_speakers=2"
```

## 🐳 Déploiement avec Coolify

### Méthode 1 : Docker Compose dans Coolify

1. **Dans Coolify Dashboard :**
   - New Service > Docker Compose
   - Upload votre `docker-compose.yml`

2. **Variables d'environnement :**
   - Ajoutez `HF_TOKEN` si vous utilisez la diarisation
   - Coolify gère automatiquement le routing (pas besoin de configurer le port)

3. **Important :** 
   - Le port n'est pas mappé dans docker-compose.yml (Coolify gère via Traefik)
   - Si vous avez un conflit de port, arrêtez l'ancien service Whisper d'abord

4. **Déployer :**
   - Cliquez sur Deploy
   - Attendez que le healthcheck passe (40s max)
   - Accédez via le domaine configuré dans Coolify

### Méthode 2 : Script de déploiement

```bash
# Sur votre serveur
./deploy.sh up
```

## 🛠️ Commandes Utiles

### Gestion du service

```bash
# Démarrer
./deploy.sh up

# Arrêter
./deploy.sh down

# Voir les logs
./deploy.sh logs

# Sauvegarder les données
./deploy.sh backup

# Restaurer depuis une sauvegarde
./deploy.sh restore ./backups/scriberr_backup_20240101_120000.tar.gz
```

### Commandes Docker directes

```bash
# Voir les logs
docker-compose logs -f

# Redémarrer
docker-compose restart

# Voir le statut
docker-compose ps

# Accéder au conteneur
docker exec -it scriberr sh
```

## 📁 Structure des Données

```
.
├── docker-compose.yml    # Configuration Docker Compose
├── .env                  # Variables d'environnement (à créer)
├── .env.example          # Exemple de configuration
├── deploy.sh             # Script de déploiement
├── data/                 # Données persistantes
│   ├── scriberr.db      # Base de données
│   └── uploads/         # Fichiers uploadés
└── backups/              # Sauvegardes (créé automatiquement)
```

## ⚙️ Configuration Avancée

### Support GPU NVIDIA

Pour activer le support GPU, décommentez la section dans `docker-compose.yml` :

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

**Prérequis :**
- NVIDIA Docker runtime installé
- GPU compatible CUDA

### Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `HF_TOKEN` | Token HuggingFace pour diarisation | (vide) |
| `PORT` | Port d'écoute | `8080` |
| `DB_PATH` | Chemin de la base de données | `/app/data/scriberr.db` |
| `UPLOAD_DIR` | Répertoire d'upload | `/app/data/uploads` |

## 🔒 Sécurité

- Les fichiers uploadés sont stockés localement dans `./data/uploads`
- La base de données est dans `./data/scriberr.db`
- Configurez un reverse proxy (Nginx/Traefik) pour HTTPS en production
- Utilisez des variables d'environnement pour les tokens sensibles

## 🐛 Dépannage

### Le service ne démarre pas

```bash
# Vérifier les logs
./deploy.sh logs

# Vérifier les ports
netstat -tulpn | grep 8080

# Vérifier Docker
docker ps -a
```

### Erreur de diarisation

- Vérifiez que `HF_TOKEN` est correctement configuré dans `.env`
- Vérifiez que le token est valide sur HuggingFace
- La diarisation fonctionne sans token mais avec des limitations

### Problèmes de mémoire

- Scriberr est optimisé pour les longs fichiers
- Si problèmes, augmentez la RAM allouée à Docker
- Considérez l'utilisation d'un GPU pour de meilleures performances

## 📊 Performance

- **CPU** : Transcription en temps réel × 0.5-1x (selon modèle)
- **RAM** : ~2-4GB pour les fichiers moyens
- **GPU** : Accélération significative si disponible
- **Longs podcasts** : Optimisé pour fichiers >1h

## 🔄 Migration depuis Whisper

Si vous migrez depuis un ancien service Whisper :

1. **Sauvegardez vos données :**
```bash
# Depuis l'ancien projet
tar -czf whisper_backup.tar.gz ./logs ./models
```

2. **Déployez Scriberr :**
```bash
./deploy.sh up
```

3. **Migrez les transcriptions (optionnel) :**
   - Utilisez l'API Scriberr pour re-transcrire si nécessaire
   - Les anciens fichiers peuvent être uploadés via l'interface web

## 📚 Ressources

- [Scriberr GitHub](https://github.com/rishikanthc/scriberr)
- [WhisperX Documentation](https://github.com/m-bain/whisperX)
- [HuggingFace Tokens](https://huggingface.co/settings/tokens)

## 📝 Notes

- Les données sont persistantes dans `./data/`
- Faites des sauvegardes régulières avec `./deploy.sh backup`
- Le healthcheck vérifie `/health` toutes les 30s
- Le service redémarre automatiquement en cas d'erreur

## 🆘 Support

Pour toute question ou problème :
1. Vérifiez les logs : `./deploy.sh logs`
2. Consultez la documentation Scriberr
3. Vérifiez les issues GitHub du projet

---

**Fait avec ❤️ pour les longs podcasts**
