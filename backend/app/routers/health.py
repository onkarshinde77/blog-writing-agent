import json
from typing import Any
from urllib.request import urlopen
from fastapi import APIRouter
from src.config import DEFAULT_MODEL, MODEL_OPTIONS, OLLAMA_BASE_URL
router=APIRouter()

@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "editorial-studio-api"}


# List supported local models and whether Ollama has them installed.

@router.get("/api/models")
def local_models() -> dict[str, Any]:
    installed: set[str] = set()
    ollama_online = False
    try:
        with urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        installed = {item.get("name", "") for item in payload.get("models", [])}
        ollama_online = True
    except Exception:
        pass
    models = [
        {
            "id": model_id,
            "label": label,
            "installed": model_id in installed or f"{model_id}:latest" in installed,
        }
        for model_id, label in MODEL_OPTIONS.items()
    ]
    return {"models": models, "default": DEFAULT_MODEL, "ollama_online": ollama_online}


# Return the dashboard's sign-in requirements and current session state.

