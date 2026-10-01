# RepoGrill

Paste a GitHub repo. Get grilled on it, out loud, by an interviewer who has actually read your code.

> Work in progress: see the sections below as they fill in.

## Features

- Reads a public GitHub repo and builds a project dossier
- Voice interview with adaptive follow-ups
- Scorecard that catches technical claims your code doesn't back up

## Project layout

```
backend/   FastAPI service (ingestion, dossier, interview engine, scoring)
frontend/  Next.js app (landing, interview, report)
```

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env             # then set LLM_API_KEY
python scripts/discover_models.py --write
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## License

MIT
