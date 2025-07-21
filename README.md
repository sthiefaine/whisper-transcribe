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

## Gestion asynchrone des transcriptions (proposition pour évolution future)

### Objectif
Permettre de traiter des fichiers audio très longs sans risque de timeout HTTP, en lançant la transcription en tâche de fond et en permettant au client de suivre l’avancement puis de récupérer le résultat.

### Principe général
1. **POST `/transcribe-async`**
   - Le client envoie un fichier audio ou une URL.
   - Le serveur crée une tâche asynchrone (thread ou process Python).
   - Le serveur répond immédiatement avec un `task_id` unique.

2. **GET `/transcription-status/<task_id>`**
   - Le client interroge l’état de la tâche (`pending`, `processing`, `done`, `error`).
   - L’état est stocké en mémoire (dictionnaire partagé) ou dans un petit fichier JSON.

3. **GET `/transcriptions/<fichier>.txt`**
   - Quand la tâche est terminée, le client peut télécharger la transcription comme aujourd’hui.

### Exemple de logique côté serveur (pseudo-code)

```python
# Dictionnaire global pour stocker l’état des tâches
TASKS = {}

@app.route('/transcribe-async', methods=['POST'])
def transcribe_async():
    # 1. Générer un task_id unique
    # 2. Stocker l’état initial (pending)
    # 3. Lancer un thread/process qui exécute la transcription et met à jour l’état
    # 4. Retourner le task_id
    pass

@app.route('/transcription-status/<task_id>', methods=['GET'])
def transcription_status(task_id):
    # Retourner l’état de la tâche (pending, processing, done, error)
    pass
```

### Avantages
- Plus de timeout HTTP, même pour des fichiers très longs.
- Facile à intégrer à l’API existante.
- Peut évoluer vers une solution plus robuste (Celery/Redis) si besoin.

### Limites
- Si le serveur redémarre, les tâches en mémoire sont perdues (prévoir une persistance sur disque si besoin).
- Pour une forte charge ou plusieurs serveurs, préférer une file d’attente externe (ex: Redis).

### Pour aller plus loin
- Ajouter une persistance des tâches sur disque (fichier JSON par tâche).
- Passer à Celery/Redis pour la scalabilité.
- Ajouter des notifications (webhook, email) quand la transcription est prête.

--- 

## Formats de sortie disponibles

L’API permet de choisir le format de sortie de la transcription :
- `txt` : texte brut (par défaut)
- `srt` : sous-titres SRT (avec timestamps, compatible vidéo)
- `vtt` : WebVTT (pour affichage synchronisé sur le web)

### Utilisation du paramètre `output_format`

Ajoutez le champ `output_format` dans votre requête JSON ou formulaire :

#### Exemple pour `/transcribe` ou `/transcribe-async`
```json
{
  "audio_url": "https://.../fichier.mp3",
  "model": "base",
  "language": "fr",
  "output_format": "vtt"
}
```

#### Exemple pour `/transcribe/file` (upload)
- Ajoutez un champ `output_format` dans le formulaire (valeur : `txt`, `srt` ou `vtt`).

### Résultat
- Le lien de transcription pointera vers le fichier généré au bon format :
  - `.txt` pour le texte brut
  - `.srt` pour les sous-titres SRT
  - `.vtt` pour le format WebVTT

### Affichage synchronisé (paroles, karaoké, etc.)
- Utilisez le format `srt` ou `vtt` pour afficher les paroles synchronisées avec l’audio dans un lecteur compatible (HTML5, Video.js, Plyr, etc.).
- Le format `txt` ne contient que le texte sans timestamps.

--- 