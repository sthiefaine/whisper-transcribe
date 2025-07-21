# 🎤 Whisper Service - La Boîte de Chocolat

Service de transcription audio utilisant Whisper.cpp pour le podcast "La Boîte de Chocolat".

## 🚀 Déploiement

### Démarrage Rapide (Recommandé)
```bash
# Cloner le projet
git clone https://github.com/votre-username/laboitedechocolat-whisper.git
cd laboitedechocolat-whisper

# Démarrage automatique
npm start

# Test rapide
npm run test-quick
```

### Avec Docker Compose (Local)
```bash
# Démarrer les services
npm run up

# Vérifier les logs
npm run logs
```

### Avec Railway (Recommandé)
1. Connectez votre repo GitHub à Railway
2. Railway détectera automatiquement le Dockerfile
3. Déployez !

### Avec Render
1. Créez un nouveau Web Service
2. Connectez votre repo GitHub
3. Sélectionnez "Docker" comme runtime
4. Déployez !

## 📡 API

### Transcription
```bash
POST /transcribe
Content-Type: application/json

{
  "audio_url": "https://example.com/audio.mp3",
  "language": "fr",
  "model": "base"
}
```

**Réponse :**
```json
{
  "success": true,
  "transcription": "Voici le texte transcrit...",
  "model": "whisper-base-fr",
  "processing_time": 12.34,
  "file_size": 1024000
}
```

### Health Check
```bash
GET /health
```

**Réponse :**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "model": "whisper-base-fr",
  "version": "1.0.0"
}
```

### Lister les Modèles
```bash
GET /models
```

**Réponse :**
```json
{
  "models": ["ggml-base.bin"],
  "current_model": "ggml-base.bin"
}
```

## 📤 Gestion des longues transcriptions

Pour les fichiers audio générant une transcription longue (plus de 2000 caractères), l’API **ne renvoie pas tout le texte dans la réponse**. À la place :

- La transcription est stockée côté serveur dans `/var/log/whisper/`.
- L’API renvoie une clé `transcription_url` permettant de télécharger le texte.
- Pour les transcriptions courtes, le texte est renvoyé directement dans la réponse.

### Exemple de réponse pour une longue transcription
```json
{
  "success": true,
  "transcription_url": "https://api.ton-domaine.com/transcriptions/12345678-90ab-cdef-1234-567890abcdef.txt",
  "model": "whisper-large-fr",
  "processing_time": 123.45,
  "file_size": 12345678
}
```

### Pour récupérer la transcription

Il suffit d’accéder à l’URL fournie :
```
GET /transcriptions/<transcription_id>.txt
```

---

## 🔀 Différence entre `/transcribe` et `/transcribe/file`

- **`/transcribe/file`** : upload direct d’un fichier audio (multipart/form-data)
- **`/transcribe`** : envoi d’une URL d’audio à télécharger (JSON)

Les deux routes appliquent la même logique : stockage + URL pour les longues transcriptions, texte direct pour les courtes.

## 🔧 Configuration

### Variables d'environnement
- `PORT` : Port du serveur (défaut: 8080)
- `MAX_FILE_SIZE` : Taille max des fichiers (défaut: 100MB)
- `WHISPER_PATH` : Chemin vers Whisper.cpp (défaut: /opt/whisper.cpp)

### Modèles Disponibles
- `base` : Modèle de base (recommandé)
- `small` : Modèle plus petit, plus rapide
- `medium` : Modèle plus grand, plus précis
- `large` : Modèle le plus précis (nécessite plus de RAM)

## 📊 Monitoring

- Health check automatique toutes les 30s
- Logs structurés avec timestamps
- Métriques de performance (temps de traitement)
- Gestion des erreurs et timeouts

## 🛠️ Développement

### Scripts NPM
Le projet utilise npm pour centraliser tous les scripts :

```bash
# Voir tous les scripts disponibles
npm run help

# Commandes principales
npm start          # Démarrage automatique
npm run test-quick # Test rapide
npm run logs       # Voir les logs
npm run reset      # Reset complet
```

### Fichier de Test
Le projet inclut un fichier de test audio `data/avatar_test_short.mp3` (145MB) pour tester la transcription :
```bash
# Vérifier le fichier
ls -lh data/avatar_test_short.mp3

# Test rapide
npm run test-quick
```

### Structure du Projet
```
laboitedechocolat-whisper/
├── Dockerfile              # Image Docker
├── docker-compose.yml      # Orchestration
├── server.py              # Serveur Flask
├── requirements.txt       # Dépendances Python
├── nginx.conf            # Configuration Nginx
├── .gitignore           # Fichiers ignorés
├── README.md            # Documentation
└── scripts/             # Scripts utilitaires
    ├── install-whisper.sh
    └── download-models.sh
```

### Tests Locaux

#### Test avec Docker
```bash
# Démarrer les services
npm run up

# Test rapide
npm run test-quick

# Test complet
npm test

# Vérifier la santé
npm run test-health
```

#### Test sans Docker (développement)
```bash
# Mode développement
npm run dev

# Dans un autre terminal, tester
npm run test-local
```

#### Test manuel avec curl
```bash
# Test avec fichier local
curl -X POST http://localhost:8080/transcribe/file \
  -F "audio_file=@data/avatar_test_short.mp3" \
  -F "language=fr" \
  -F "model=base"

# Test avec URL
curl -X POST http://localhost:8080/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_url": "https://example.com/test.mp3"}'
```

## 🔒 Sécurité

- Utilisateur non-root dans le conteneur
- Validation des URLs d'entrée
- Limitation de la taille des fichiers
- Timeouts configurés
- CORS configuré (à adapter en production)

## 📈 Performance

- Modèle base : ~1GB RAM, ~10-30s pour 1min d'audio
- Optimisé pour les podcasts français
- Support des formats audio courants (MP3, WAV, M4A)
- Traitement asynchrone possible

## 🤝 Intégration

### Avec votre projet principal
```typescript
// Dans votre projet laboitedechocolat
const WHISPER_API_URL = process.env.WHISPER_API_URL || "http://localhost:8080";

const response = await fetch(`${WHISPER_API_URL}/transcribe`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    audio_url: audioFileUrl,
    language: 'fr',
    model: 'base'
  })
});
```

## 🐛 Dépannage

### Problèmes Courants

1. **Modèle non trouvé**
   ```bash
   # Vérifier que le modèle est téléchargé
   docker-compose exec whisper-api ls /opt/whisper.cpp/models/
   ```

2. **Timeout de transcription**
   - Augmenter les timeouts dans nginx.conf
   - Vérifier la taille du fichier audio

3. **Erreur de compilation**
   ```bash
   # Reconstruire l'image
   docker-compose build --no-cache
   ```

## 📝 Licence

MIT License - Libre d'utilisation pour le projet "La Boîte de Chocolat" 

## 📦 Modèles Disponibles
- `tiny` : Modèle ultra-rapide, peu précis
- `base` : Modèle de base (recommandé pour la plupart des usages)
- `small` : Plus précis, un peu plus lent
- `medium` : Très précis, plus lent
- `large` : Le plus précis, très gourmand en RAM/CPU
- `large-v2` : Variante améliorée du modèle large

## 📥 Télécharger tous les modèles Whisper

Pour télécharger tous les modèles sur votre serveur (après déploiement) :

```bash
bash scripts/download-all-models.sh
```

Les modèles seront placés dans `/opt/whisper.cpp/models` (ou le volume Docker correspondant).

## 📡 Exemple d'appel API avec un modèle spécifique

### Transcription avec le modèle large

```bash
curl -X POST http://localhost:8080/transcribe/file \
  -F "audio_file=@data/avatar_test_short.mp3" \
  -F "language=fr" \
  -F "model=large"
```

## 🐳 Astuce Docker/Coolify

- Les modèles téléchargés sont persistants si vous utilisez un volume Docker pour `/opt/whisper.cpp/models`.
- Après chaque déploiement, vérifiez la présence des modèles avec :
  ```bash
  docker-compose exec whisper-api ls /opt/whisper.cpp/models/
  ``` 