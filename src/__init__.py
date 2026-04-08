"""
Blog Writing Agent - Main Package
AI agent for generating technical blog posts automatically.
"""
from src.config import model, CONFIG
from src.graph import app

__version__ = "1.0.0"
__all__ = ["model", "CONFIG", "app"]
