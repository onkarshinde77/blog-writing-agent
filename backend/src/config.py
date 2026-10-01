"""Application configuration and local Ollama chat model factory."""
from __future__ import annotations
import os
from functools import lru_cache
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
load_dotenv()

MODEL_OPTIONS = {
    "qwen3.5:4b": "qwen3.5:4b",
    "qwen3:1.7b": "qwen3:1.7b",
}
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
if DEFAULT_MODEL not in MODEL_OPTIONS:
    DEFAULT_MODEL = "qwen3.5:4b"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


@lru_cache(maxsize=len(MODEL_OPTIONS))
def get_model(model_name: str | None = None) -> ChatOllama:
    """Get the configured Ollama model, rejecting names outside the UI allowlist."""
    name = model_name or DEFAULT_MODEL
    if name not in MODEL_OPTIONS:
        raise ValueError(f"Unsupported local model: {name}")
    return ChatOllama(
        model=name,
        base_url=OLLAMA_BASE_URL,
        temperature=0.3,
    )


# Application Configuration
CONFIG = {
    "configurable": {"thread_id": "blog-1"},
    "run_name": "blog-writing-agent",
}
