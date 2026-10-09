# Research_Pal

An AI app that reads your research papers and fills a reading card for each one:
**My question, Problem, Method, Result, Limitation, Use.**
Every claim has a quote from the PDF, and the server checks each quote against the real text.

## Links

| What | Link |
|---|---|
| Live app | https://rsearch-pal-7tor.vercel.app/ |
| Backend API (health check) | https://research-pal-api.onrender.com/api/health |
| Source code | https://github.com/zarsalene/rsearch_pal |
| Full documentation | [research-pal/README.md](research-pal/README.md) |
| How to test | [research-pal/docs/TESTING.md](research-pal/docs/TESTING.md) |

The live app uses free plans. The server sleeps after 15 minutes without use, so the first request can take up to one minute. The free disk is temporary: download a backup in **Settings** every week.

## What is in this repository

```
research-pal/backend/    FastAPI + ChromaDB + pypdf. AI through Gemini, Groq, OpenRouter or Ollama.
research-pal/frontend/   React (Vite). Also the base of the phone app (Capacitor).
research-pal/render.yaml Settings for Render (backend).
research-pal/docs/       Sprint reports, tests, design notes.
.github/workflows/       CI: GitHub runs all tests on each push.
```

## Quick start

```bash
cd research-pal/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then edit: APP_PASSWORD, SECRET_KEY, GEMINI_API_KEY, GROQ_API_KEY
set -a && source .env && set +a
uvicorn app.main:app --reload --port 8000
```

```bash
cd research-pal/frontend
cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm install
npm run dev              # open http://localhost:5173
```

Read [research-pal/README.md](research-pal/README.md) for the rules of the app, how to put it online for free, the limits of the free plans, and privacy.
