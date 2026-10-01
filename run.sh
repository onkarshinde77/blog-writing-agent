#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000


ollama list                  → installed models
ollama ps                    → currently running models
ollama run qwen3.5:4b        → start/use model
ollama stop qwen3.5:4b       → stop model
ollama pull qwen3.5:4b       → download model
ollama rm qwen3.5:4b         → delete model
ollama serve                 → start Ollama server