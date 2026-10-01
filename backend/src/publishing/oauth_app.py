"""Standalone backend host for authenticated publishing OAuth endpoints."""
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from src.publishing.linkedin_oauth import router

app = FastAPI(title="Blog Publisher OAuth", docs_url=None, redoc_url=None)
app.include_router(router)
