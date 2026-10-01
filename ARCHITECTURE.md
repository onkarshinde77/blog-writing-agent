# Architecture

```text
Browser
  └── React + Vite (frontend/)
       ├── /api/*  ───────────────┐
       └── /auth/*                 │
                                   ▼
                         FastAPI (backend/app/)
                           ├── workflow job and local-model API
                           ├── review and publish actions
                           ├── existing OAuth router
                           └── static frontend build in production
                                   │
                                   ▼
                         LangGraph (backend/src/)
                           ├── topic analysis and routing
                           ├── conditional research
                           ├── planning and writing
                           ├── quality gate and review
                           └── human approval and publishers
                                   │
                                   ▼
                         SQLite checkpoints and history
```

## Frontend

`frontend/` contains the React application, presentation styles, API client, and Vite configuration. During development Vite proxies API and OAuth requests to FastAPI. A production Vite build is served by FastAPI from `frontend/dist`.

## Backend

`backend/app/main.py` exposes health, blog history, workflow progress, approval actions, publishing status, and login endpoints. Long LangGraph runs execute in a small worker pool; the API reads progress and approval interrupts from the same persisted thread checkpoint. OAuth continues to use the existing HTTP Basic protected router.

`backend/src/` contains the existing LangChain prompts, graph nodes, review and publishing adapters, OAuth token store, and blog-history helpers. Relative `PUBLISHING_DB_PATH` values remain relative to the repository root, so moving the code does not move the project's existing database.

The model selector chooses an allowlisted Ollama model per workflow. That choice is carried through planning, writing, quality checks, review, and LinkedIn drafting; it does not change another running workflow. `OLLAMA_BASE_URL` and `OLLAMA_MODEL` configure the local server and initial selection.

## Trust boundaries

- Provider credentials and encrypted OAuth tokens remain on the backend.
- Review and publishing actions require the configured `PUBLISHING_UI_PASSWORD` session when set.
- OAuth endpoints retain `PUBLISHING_WEB_USER` and `PUBLISHING_WEB_PASSWORD` HTTP Basic authentication.
- The workflow owns factual checks, review reports, human approvals, publication retries, and idempotency. The React UI displays backend-returned results without calculating review scores.
