# World Watcher

Real-time monitoring dashboard with async workers, AI analysis, alerts, and a voice assistant.

> Implementation in progress. This repo is being built from the spec in `claude.md`.

## Stack
- Python 3.11, FastAPI, asyncio
- React + Vite
- SQLite
- Provider-independent AI (OpenAI/Anthropic/local)

## Quick Start (local)

### 1. Environment
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

### 2. Backend
```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000
```

### 3. Frontend
```powershell
cd frontend
npm install
npm run dev
```

## Docker (planned)
`Dockerfile` and `docker-compose.yml` will be added during hardening phase.

## Testing
```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

## Notes
- All secrets/config come from `.env`; never commit `.env`.
- Desktop notifications may be unavailable in containers; dashboard alerts remain available.
