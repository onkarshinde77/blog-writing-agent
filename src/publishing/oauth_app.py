"""Standalone backend host for the authenticated LinkedIn OAuth endpoints."""
from fastapi import FastAPI
from src.publishing.linkedin_oauth import router

app = FastAPI(title="Blog Publisher OAuth", docs_url=None, redoc_url=None)
app.include_router(router)
