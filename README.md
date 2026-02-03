# Podcast Transcriber

Système de transcription robuste pour podcasts longs (1h30-2h+) avec support des checkpoints et reprise après crash.

## Fonctionnalités

- **Transcription par chunks**: Découpe l'audio en segments de 5 minutes, traités individuellement
- **Checkpoints automatiques**: Sauvegarde après chaque chunk, reprise possible après crash/restart
- **Speaker Diarization**: Identification des différents speakers (pyannote-audio)
- **Modèle Whisper large-v3**: Meilleure qualité de transcription disponible
- **Interface web**: Upload, suivi du progrès en temps réel, visualisation du transcript
- **Export multiple**: TXT, SRT, VTT, JSON

## Pourquoi ce projet ?

Sur un petit serveur (Hetzner CCX23), transcrire un podcast de 2h avec Whisper large-v3 peut prendre 24-32h. Les solutions existantes comme Scriberr échouent car le processus est tué après quelques heures.

Cette solution découpe l'audio en chunks et sauvegarde le progrès après chaque chunk. Si le serveur redémarre ou le processus crash, la transcription reprend au dernier chunk terminé.

## Installation

### Prérequis

- Docker & Docker Compose
- Token HuggingFace (pour la diarization) - [Obtenir un token](https://huggingface.co/settings/tokens)
- Accepter les conditions pyannote: https://huggingface.co/pyannote/speaker-diarization-3.1

### Configuration

```bash
# Copier le fichier d'exemple
cp env.example .env

# Éditer .env et ajouter votre HF_TOKEN
nano .env
```

### Lancement

```bash
# Build et démarrage
docker-compose up -d --build

# Voir les logs
docker-compose logs -f backend
```

L'interface est accessible sur http://localhost:8080

### Déploiement Coolify

Pour déployer sur Coolify/Hetzner:

```bash
# Utiliser la configuration Coolify
docker-compose -f docker-compose.coolify.yml up -d --build
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React/Vite)                    │
│  Upload | Jobs List | Progress Bar | Transcript Viewer      │
└────────────────────────────┬────────────────────────────────┘
                             │ REST + WebSocket
┌────────────────────────────▼────────────────────────────────┐
│                   Backend (FastAPI)                         │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │ Job Manager  │  │ Chunk Processor│  │ Checkpoint Mgr  │  │
│  │   (SQLite)   │  │(faster-whisper)│  │   (SQLite)      │  │
│  └──────────────┘  └───────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/jobs | Upload audio + créer job |
| GET | /api/jobs | Liste des jobs |
| GET | /api/jobs/{id} | Détails d'un job |
| POST | /api/jobs/{id}/resume | Reprendre un job |
| POST | /api/jobs/{id}/cancel | Annuler un job |
| DELETE | /api/jobs/{id} | Supprimer un job |
| GET | /api/jobs/{id}/transcript | Récupérer le transcript |
| GET | /api/jobs/{id}/transcript/download?format=srt | Télécharger |
| WS | /ws/progress/{id} | Progress temps réel |

## Configuration

Variables d'environnement:

| Variable | Default | Description |
|----------|---------|-------------|
| HF_TOKEN | - | Token HuggingFace (requis pour diarization) |
| MODEL_SIZE | large-v3 | Modèle Whisper |
| DEVICE | cpu | cpu ou cuda |
| COMPUTE_TYPE | int8 | int8 (CPU) ou float16 (GPU) |
| CHUNK_DURATION | 300 | Durée chunk en secondes |
| CPU_THREADS | 4 | Threads CPU |

## Temps estimés (podcast 2h sur CCX23)

| Phase | Durée | RAM |
|-------|-------|-----|
| Chunking | 2-3 min | ~500MB |
| Transcription | 20-30h | ~4GB |
| Diarization | 30-60 min | ~3GB |
| **Total** | **~24-32h** | **4GB max** |

Mais contrairement aux autres solutions, si le processus crash, il reprend là où il s'est arrêté !

## Développement

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI endpoints
│   ├── config.py            # Configuration
│   ├── database.py          # SQLite models
│   └── services/
│       ├── audio_chunker.py # FFmpeg splitting
│       ├── transcriber.py   # faster-whisper
│       ├── diarizer.py      # pyannote-audio
│       ├── checkpoint.py    # Checkpoint manager
│       └── job_processor.py # Orchestration

frontend/
├── src/
│   ├── components/
│   │   ├── UploadPanel.tsx
│   │   ├── JobList.tsx
│   │   ├── ProgressBar.tsx
│   │   └── TranscriptViewer.tsx
│   └── hooks/
│       └── useWebSocket.ts
```

## License

MIT
