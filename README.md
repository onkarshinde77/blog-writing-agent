# ONKAR AI Editorial Studio

An AI editorial workflow with a **React + Vite frontend** and a **FastAPI + LangGraph backend**. The agent can research a topic, plan and write an article, run its existing quality checks, and wait for a person to approve it before publishing.

## Project layout

```text
backend/
  app/main.py           FastAPI API, workflow jobs, review actions, static app serving
  src/                  LangChain nodes, LangGraph workflow, history, OAuth, publishing
  requirements.txt      Python backend dependencies
frontend/
  src/                  React pages and components
  package.json          Vite and frontend dependencies
tests/                  Existing backend publishing tests
.env.example            Backend environment variable template
```

## Local development

Use two terminals from the repository root. Python 3.11 or newer and Node.js 18 or newer are recommended.

### 1. Install and start the backend

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

On macOS or Linux, activate with `source .venv/bin/activate` instead.

### 2. Install and start the frontend

```powershell
npm install --prefix frontend
npm run dev --prefix frontend
```

Open the Vite URL printed in the terminal (normally `http://127.0.0.1:5173`). Vite forwards `/api` and `/auth` requests to the local FastAPI server.

Copy `.env.example` to `.env` and configure `GROQ_API_KEY` and `TAVILY_API_KEY` for generation and research. Provider keys, OAuth credentials, and database settings stay on the backend. Keep `.env` private.

## Production build

Build the React assets and start FastAPI from the repository root:

```powershell
npm install --prefix frontend
npm run build --prefix frontend
python -m pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

FastAPI serves the generated `frontend/dist` app and the `/api` endpoints from one origin. Configure HTTPS at the deployment proxy, set `COOKIE_SECURE=true`, and provide `FRONTEND_ORIGINS` if the frontend is hosted on a separate origin. The SQLite database remains at the repository-root path selected by `PUBLISHING_DB_PATH`; its existing relative-path behavior is preserved.

## Authentication and publishing

- Set `PUBLISHING_UI_PASSWORD` to protect review decisions and OAuth connection actions in the studio.
- The existing OAuth API continues to use HTTP Basic credentials from `PUBLISHING_WEB_USER` and `PUBLISHING_WEB_PASSWORD`.
- Set `TOKEN_ENCRYPTION_KEY` to a Fernet key before connecting OAuth accounts. OAuth tokens remain encrypted in the existing SQLite database.
- Configure WordPress.com and LinkedIn OAuth with their existing client IDs, client secrets, site details, and registered callback URLs. DEV.to publishing uses `DEV_API_KEY`.
- Article publishing runs through the existing adapters only after human approval. LinkedIn keeps its separate post approval step.

Useful variables are listed in `.env.example`. The backend exposes a health check at `/api/health`; FastAPI’s API schema is available at `/docs` during development.

## Existing workflow

The FastAPI layer wraps the existing LangGraph application and SQLite checkpoints. It adds API endpoints for article history, workflow progress, review decisions, and publishing status. LangChain prompts, graph nodes, publishers, OAuth routes, and saved blog history remain in `backend/src`.
