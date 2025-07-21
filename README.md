# Whisper Transcription API

API de transcription audio utilisant Whisper.cpp pour convertir des fichiers audio en texte avec support de multiples formats de sortie.

## Fonctionnalités

- Transcription audio en temps réel et asynchrone
- Support de multiples formats de sortie (TXT, SRT, VTT)
- Gestion automatique du nettoyage des fichiers (>24h)
- Limitation de concurrence (1 transcription à la fois)
- Support de multiples modèles Whisper
- Interface web simple pour upload de fichiers

## Installation et Déploiement

### Prérequis

- Docker et Docker Compose
- Modèles Whisper (téléchargés automatiquement ou manuellement)

### Déploiement

1. Clonez le repository
2. Configurez les variables d'environnement (voir `env.example`)
3. Lancez avec Docker Compose :
```bash
docker-compose up -d
```

## Documentation API pour LLM

### Endpoints Principaux

#### 1. POST /transcribe
Transcription synchrone d'un fichier audio depuis une URL.

**Paramètres JSON :**
```json
{
  "audio_url": "https://example.com/audio.mp3",
  "language": "fr",
  "model": "large-v3-turbo-q8_0",
  "output_format": "srt",
  "word_thold": 0.005,
  "no_speech_thold": 0.40
}
```

**Paramètres :**
- `audio_url` (requis) : URL du fichier audio à transcrire
- `language` (optionnel) : Code langue (défaut: "fr")
- `model` (optionnel) : Modèle Whisper (défaut: "base")
- `output_format` (optionnel) : Format de sortie ("txt", "srt", "vtt", défaut: "txt")
- `word_thold` (optionnel) : Seuil de confiance des mots (défaut: 0.005)
- `no_speech_thold` (optionnel) : Seuil de détection de parole (défaut: 0.40)
- `prompt` (optionnel) : Contexte initial pour améliorer la transcription (ex: "podcast cinéma Avatar")

**Réponse :**
```json
{
  "transcription": "Contenu transcrit...",
  "transcription_url": "https://api.example.com/transcriptions/fichier__uuid.txt",
  "model_used": "large-v3-turbo-q8_0",
  "language": "fr",
  "processing_time": 12.5
}
```

#### 2. POST /transcribe/file
Transcription synchrone d'un fichier audio uploadé.

**Paramètres Form-Data :**
- `audio_file` (requis) : Fichier audio
- `language` (optionnel) : Code langue
- `model` (optionnel) : Modèle Whisper
- `output_format` (optionnel) : Format de sortie
- `word_thold` (optionnel) : Seuil de confiance des mots
- `no_speech_thold` (optionnel) : Seuil de détection de parole

**Réponse :** Identique à `/transcribe`

#### 3. POST /transcribe-async
Transcription asynchrone pour fichiers longs.

**Paramètres JSON :**
```json
{
  "audio_url": "https://example.com/long-audio.mp3",
  "language": "fr",
  "model": "large-v3-turbo-q8_0",
  "output_format": "srt",
  "word_thold": 0.005,
  "no_speech_thold": 0.40
}
```

**Réponse initiale :**
```json
{
  "task_id": "uuid-task-id",
  "status_url": "/transcription-status/uuid-task-id"
}
```

#### 4. GET /transcription-status/{task_id}
Vérification du statut d'une transcription asynchrone.

**Réponse :**
```json
{
  "status": "processing",
  "progress": 45,
  "result": null
}
```

**Statuts possibles :**
- `pending` : En attente
- `processing` : En cours (avec pourcentage)
- `completed` : Terminé
- `failed` : Échec

**Réponse finale (completed) :**
```json
{
  "status": "completed",
  "progress": 100,
  "result": {
    "transcription": "Contenu transcrit...",
    "transcription_url": "https://api.example.com/transcriptions/fichier__uuid.srt",
    "model_used": "large-v3-turbo-q8_0",
    "language": "fr",
    "processing_time": 125.3
  }
}
```

#### 5. GET /health
Vérification de l'état de l'API.

**Réponse :**
```json
{
  "status": "healthy",
  "active_transcriptions": 0,
  "max_concurrent": 1
}
```

#### 6. GET /transcriptions/{filename}
Téléchargement d'un fichier de transcription.

### Modèles Disponibles

- `base` : Modèle de base (rapide, moins précis)
- `small` : Modèle petit (équilibré)
- `medium` : Modèle moyen (bon équilibre)
- `large-v3` : Modèle large (très précis, lent)
- `large-v3-turbo-q8_0` : Modèle large optimisé (recommandé)

### Formats de Sortie

#### TXT (texte simple)
```
Maman disait toujours, la vie c'est comme une boîte de chocolat.
On ne sait jamais sur quoi on va tomber.
```

#### SRT (sous-titres)
```
1
00:00:00,500 --> 00:00:04,880
Maman disait toujours, la vie c'est comme une boîte de chocolat.

2
00:00:04,880 --> 00:00:07,800
On ne sait jamais sur quoi on va tomber.
```

#### VTT (WebVTT)
```
WEBVTT

00:00:00.500 --> 00:00:04.880
Maman disait toujours, la vie c'est comme une boîte de chocolat.

00:00:04.880 --> 00:00:07.800
On ne sait jamais sur quoi on va tomber.
```

### Codes d'Erreur

- `400 Bad Request` : Paramètres manquants ou invalides
- `429 Too Many Requests` : Transcription déjà en cours
- `500 Internal Server Error` : Erreur serveur

### Exemples d'Utilisation

#### Transcription simple
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "audio_url": "https://example.com/audio.mp3",
  "language": "fr",
  "output_format": "srt",
  "prompt": "podcast cinéma Avatar James Cameron"
}' http://api.example.com/transcribe
```

#### Transcription asynchrone
```bash
# Démarrer la transcription
curl -X POST -H "Content-Type: application/json" -d '{
  "audio_url": "https://example.com/long-audio.mp3",
  "model": "large-v3-turbo-q8_0",
  "output_format": "vtt",
  "prompt": "intelligence artificielle machine learning"
}' http://api.example.com/transcribe-async

# Vérifier le statut
curl http://api.example.com/transcription-status/task-id
```

#### Upload de fichier
```bash
curl -X POST -F "audio_file=@local-audio.mp3" \
  -F "language=fr" \
  -F "output_format=srt" \
  -F "prompt=gastronomie cuisine française" \
  http://api.example.com/transcribe/file
```

### Limitations

- **Concurrence** : Maximum 1 transcription simultanée
- **Taille de fichier** : Limite selon la configuration Nginx
- **Durée** : Pas de limite, mais recommandé <2h pour synchrone
- **Nettoyage** : Fichiers supprimés automatiquement après 24h

### Architecture

- **API Flask** : Gestion des requêtes HTTP
- **Whisper.cpp** : Moteur de transcription
- **Nginx** : Reverse proxy et gestion des fichiers statiques
- **Docker** : Conteneurisation et déploiement

### Variables d'Environnement

- `WHISPER_PATH` : Chemin vers Whisper.cpp
- `MODEL_PATH` : Chemin vers les modèles
- `MAX_CONCURRENT_TRANSCRIPTIONS` : Limite de concurrence
- `CLEANUP_HOURS` : Âge des fichiers avant suppression

## Interface Web

Accédez à `http://api.example.com/` pour l'interface web permettant l'upload de fichiers audio et la sélection des paramètres de transcription.

## Support

Pour toute question ou problème, consultez les logs Docker ou ouvrez une issue sur le repository. 