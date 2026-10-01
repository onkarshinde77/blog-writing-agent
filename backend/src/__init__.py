"""
Blog Writing Agent - Main Package
AI agent for generating technical blog posts automatically.
"""
__version__ = "1.0.0"
__all__ = ["model", "CONFIG", "app"]


def __getattr__(name):
    """Load the LLM and graph only when requested, keeping adapters importable independently."""
    if name in {"model", "CONFIG"}:
        from src import config
        return getattr(config, name)
    if name == "app":
        from src.graph import app
        return app
    raise AttributeError(name)
