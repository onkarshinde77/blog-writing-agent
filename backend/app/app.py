import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
load_dotenv()
from src.publishing.linkedin_oauth import router as oauth_router
from .routers import auth, blogs, health, publishing, workflows
from .workflow_service import recover_history

frontend_url = os.getenv("FRONTEND_ORIGINS")

app=FastAPI(title="Blog Writing Agent",version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_url,
    allow_credentials=True,
    allow_methods=["GET","POST","DELETE","OPTIONS"],
    allow_headers=["Content-Type","Authorization"]
)

all_routers = (health.router,auth.router,blogs.router,workflows.router,publishing.router,oauth_router)
for route in all_routers:
        app.include_router(route)

app.add_event_handler("startup",recover_history)
frontend_dist=Path(__file__).resolve().parents[2]/"frontend"/"dist"





def create_app() -> FastAPI:



    if frontend_dist.is_dir():
        app.mount("/assets",StaticFiles(directory=frontend_dist/"assets"),name="frontend-assets")
        @app.get("/{path:path}",include_in_schema=False)
        def frontend(path: str) -> FileResponse:
            requested=frontend_dist/path
            if path and requested.is_file() and frontend_dist in requested.resolve().parents:
                return FileResponse(requested)
            return FileResponse(frontend_dist/"index.html")
    return app

app=create_app()
