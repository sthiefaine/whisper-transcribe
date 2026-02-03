# Podcast Transcriber

Transcription de podcasts via l'API Voxtral Transcribe 2 de Mistral AI.

## Fonctionnalités

- **Voxtral Transcribe 2**: API de transcription haute qualité de Mistral AI
- **Speaker Diarization**: Identification des speakers (intégré dans Voxtral)
- **Interface web**: Upload, suivi du progrès en temps réel, visualisation du transcript
- **Export multiple**: TXT, SRT, VTT, JSON
- **Fichiers jusqu'à 1GB**: Podcasts longs supportés

## Tarification

Voxtral Transcribe 2 coûte **$0.003/minute** (~$0.36 pour un podcast de 2h).

## Installation

### Prérequis

- Docker & Docker Compose
- Clé API Mistral - [Obtenir une clé](https://console.mistral.ai/api-keys)

### Configuration

```bash
# Copier le fichier d'exemple
cp env.example .env

# Éditer .env et ajouter votre MISTRAL_API_KEY
nano .env
```

### Lancement

```bash
# Build et démarrage
docker-compose up -d --build

# Voir les logs
docker-compose logs -f backend
```

L'interface est accessible sur http://localhost:8085

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
│  ┌──────────────┐  ┌───────────────────────────────────┐   │
│  │ Job Manager  │  │     Voxtral Transcriber           │   │
│  │   (SQLite)   │  │   (Mistral AI API Client)         │   │
│  └──────────────┘  └───────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/jobs | Upload audio + créer job |
| GET | /api/jobs | Liste des jobs |
| GET | /api/jobs/{id} | Détails d'un job |
| POST | /api/jobs/{id}/retry | Réessayer un job échoué |
| POST | /api/jobs/{id}/cancel | Annuler un job |
| DELETE | /api/jobs/{id} | Supprimer un job |
| GET | /api/jobs/{id}/transcript | Récupérer le transcript |
| GET | /api/jobs/{id}/transcript/download?format=srt | Télécharger |
| WS | /ws/progress/{id} | Progress temps réel |

## Configuration

Variables d'environnement:

| Variable | Default | Description |
|----------|---------|-------------|
| MISTRAL_API_KEY | - | Clé API Mistral (requis) |
| VOXTRAL_MODEL | voxtral-mini-latest | Modèle Voxtral |
| ENABLE_DIARIZATION | true | Activer identification speakers |
| API_TIMEOUT | 3600 | Timeout API en secondes |
| MAX_FILE_SIZE | 1073741824 | Taille max fichier (1GB) |

## Temps estimés

| Durée podcast | Temps transcription | Coût |
|---------------|---------------------|------|
| 30 min | ~1-2 min | ~$0.09 |
| 1h | ~2-3 min | ~$0.18 |
| 2h | ~5-10 min | ~$0.36 |

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
│       ├── transcriber.py   # Voxtral API client
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
