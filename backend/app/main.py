"""FastAPI API for the AI Editorial Studio."""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel, Field

load_dotenv()

from src.blog_history import database_path, delete_blog_history, list_blog_history, recover_checkpoint_history
from src.graph import app as workflow
from src.markdown_math import normalize_markdown_math
from src.publishing.linkedin_oauth import router as oauth_router

logger = logging.getLogger("editorial_studio")
executor = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("WORKFLOW_WORKERS", "1"))))
jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()

app = FastAPI(title="ONKAR AI Editorial Studio", version="1.0.0")
allowed_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(oauth_router)


class BlogRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=2000)
    audience: str = Field(default="General readers", max_length=240)
    tone: str = Field(default="Clear and conversational", max_length=120)
    length: str = Field(default="Standard · about 1,000 words", max_length=120)


class ActionRequest(BaseModel):
    action: Literal["approve", "edit", "reject"]
    platforms: list[Literal["wordpress", "devto"]] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    feedback: str = Field(default="", max_length=4000)
    text: str | None = Field(default=None, max_length=3000)


def _auth_cookie(password: str) -> str:
    expires = str(int(time.time()) + 12 * 60 * 60)
    signature = hmac.new(password.encode(), expires.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def _is_authenticated(cookie: str | None) -> bool:
    password = os.getenv("PUBLISHING_UI_PASSWORD", "")
    if not password:
        return True
    if not cookie or "." not in cookie:
        return False
    expires, signature = cookie.split(".", 1)
    if not expires.isdigit() or int(expires) <= int(time.time()):
        return False
    expected = hmac.new(password.encode(), expires.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def require_publishing_auth(studio_session: str | None = Cookie(default=None)) -> None:
    if not _is_authenticated(studio_session):
        raise HTTPException(status_code=401, detail="Sign in to manage reviews and publishing.")


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _workflow_config(workflow_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": workflow_id}, "run_name": "blog-writing-agent"}


def _snapshot_cache(snapshot: Any, pending: dict[str, Any] | None) -> dict[str, Any]:
    values = snapshot.values or {}
    return {
        "topic": values.get("topic", ""),
        "final": normalize_markdown_math(values.get("final", "") or ""),
        "blog": _plain(values.get("blog_plan") or {}),
        "evidence": _plain(values.get("evidence") or []),
        "quality_report": _plain(values.get("quality_report") or {}),
        "review": _plain(values.get("review") or {}),
        "audience_analysis": _plain(values.get("audience_analysis") or {}),
        "pending": _plain(pending) if pending else None,
        "final_result": _plain(values.get("final_result") or {}),
        "published_links": _plain(values.get("published_links") or {}),
    }


def _set_job(workflow_id: str, **updates: Any) -> None:
    with jobs_lock:
        current = jobs.setdefault(workflow_id, {"workflow_id": workflow_id, "status": "queued", "node": None, "events": []})
        next_node = updates.get("node")
        if next_node and next_node != current.get("node"):
            current.setdefault("events", []).append({
                "node": next_node,
                "stage": _STAGE_MAP.get(next_node, next_node.replace("_", " ").title()),
                "status": "executed",
                "at": time.time(),
            })
        current.update(updates)
        current["updated_at"] = time.time()


_STAGE_MAP = {
    "router": "Topic analysis", "research": "Research", "topic_analysis": "Topic analysis",
    "orchestrator": "Planning", "workers": "Writing", "reducer": "Fact check",
    "quality_check": "Quality review", "quality_research": "Fact check",
    "quality_revision": "Quality review", "review": "Quality review",
    "blog_approval": "Human approval", "revision": "Writing", "publisher": "Publishing",
    "aggregate_publications": "Publishing", "linkedin_content": "Publishing",
    "linkedin_approval": "Human approval", "linkedin_publish": "Publishing", "finish": "Publishing",
}


def _run_workflow(workflow_id: str, initial: dict[str, Any] | None = None, resume: dict[str, Any] | None = None) -> None:
    _set_job(workflow_id, status="running", node="router" if initial else "review", error=None)
    config = _workflow_config(workflow_id)
    try:
        stream = workflow.stream(initial, config=config) if initial is not None else workflow.stream(Command(resume=resume), config=config)
        for update in stream:
            for node_name in update:
                _set_job(workflow_id, status="running", node=node_name)
        snapshot = workflow.get_state(config)
        interrupts = [interrupt.value for task in snapshot.tasks for interrupt in task.interrupts]
        pending = interrupts[0] if interrupts else None
        if pending:
            next_status = "awaiting_linkedin_approval" if pending.get("type") == "linkedin_approval" else "awaiting_review"
        elif snapshot.values.get("final_result"):
            next_status = "completed"
        elif not snapshot.next:
            next_status = "completed"
        else:
            next_status = "running"
        cache = _snapshot_cache(snapshot, pending)
        _set_job(workflow_id, status=next_status, node=None, error=None, state_cache=cache)
    except Exception as exc:
        logger.exception("workflow_failed workflow_id=%s error_type=%s", workflow_id, type(exc).__name__)
        _set_job(workflow_id, status="failed", node=None, error="The workflow failed. Check the backend logs and try again.", state_cache=None)


def _workflow_status(workflow_id: str) -> dict[str, Any]:
    with jobs_lock:
        job = dict(jobs.get(workflow_id, {}))
    if job.get("status") in {"queued", "running", "failed"}:
        return {
            "workflow_id": workflow_id,
            "status": job["status"],
            "stage": _STAGE_MAP.get(job.get("node")),
            "node": job.get("node"),
            "topic": job.get("topic", ""),
            "final": "", "blog": {}, "evidence": [], "quality_report": {},
            "review": {}, "audience_analysis": {}, "pending": None,
            "final_result": {}, "published_links": {}, "error": job.get("error"),
            "events": job.get("events", []),
        }
    if job.get("state_cache"):
        cached = dict(job["state_cache"])
        pending = cached.get("pending")
        cached.update({
            "workflow_id": workflow_id,
            "status": job.get("status", "completed"),
            "stage": "Human approval" if pending else None,
            "node": None,
            "error": job.get("error"),
            "events": job.get("events", []),
        })
        return cached
    try:
        snapshot = workflow.get_state(_workflow_config(workflow_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Workflow not found.") from None
    values = snapshot.values or {}
    interrupts = [interrupt.value for task in snapshot.tasks for interrupt in task.interrupts]
    pending = _plain(interrupts[0]) if interrupts else None
    if pending:
        status = "awaiting_linkedin_approval" if pending.get("type") == "linkedin_approval" else "awaiting_review"
    elif job.get("status") == "failed":
        status = "failed"
    elif job.get("status"):
        status = job["status"]
    elif not snapshot.next:
        status = "completed"
    else:
        status = "running"
    current_node = job.get("node")
    return {
        "workflow_id": workflow_id,
        "status": status,
        "stage": _STAGE_MAP.get(current_node, "Human approval" if pending else None),
        "node": current_node,
        "topic": values.get("topic", ""),
        "final": normalize_markdown_math(values.get("final", "") or ""),
        "blog": _plain(values.get("blog_plan") or {}),
        "evidence": _plain(values.get("evidence") or []),
        "quality_report": _plain(values.get("quality_report") or {}),
        "review": _plain(values.get("review") or {}),
        "audience_analysis": _plain(values.get("audience_analysis") or {}),
        "pending": pending,
        "final_result": _plain(values.get("final_result") or {}),
        "published_links": _plain(values.get("published_links") or {}),
        "events": job.get("events", []),
        "error": job.get("error"),
    }


@app.on_event("startup")
def recover_history() -> None:
    try:
        recover_checkpoint_history(workflow)
    except Exception:
        logger.exception("history_recovery_failed")
    try:
        for article in list_blog_history(limit=50):
            try:
                workflow_id = article["thread_id"]
                snapshot = workflow.get_state(_workflow_config(workflow_id))
                pending_items = [item.value for task in snapshot.tasks for item in task.interrupts]
                if not pending_items:
                    continue
                pending = pending_items[0]
                status = "awaiting_linkedin_approval" if pending.get("type") == "linkedin_approval" else "awaiting_review"
                node = "linkedin_approval" if status == "awaiting_linkedin_approval" else "blog_approval"
                _set_job(workflow_id, topic=article.get("topic", ""), status=status, node=node,
                         state_cache=_snapshot_cache(snapshot, pending), error=None)
            except Exception:
                logger.info("pending_approval_skipped workflow_id=%s", article.get("thread_id", ""))
    except Exception:
        logger.exception("pending_approval_recovery_failed")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "editorial-studio-api"}


@app.get("/api/auth/status")
def auth_status(studio_session: str | None = Cookie(default=None)) -> dict[str, bool]:
    return {"required": bool(os.getenv("PUBLISHING_UI_PASSWORD")), "authenticated": _is_authenticated(studio_session)}


class LoginRequest(BaseModel):
    password: str = Field(max_length=512)


@app.post("/api/auth/login")
def login(body: LoginRequest, response: Response) -> dict[str, bool]:
    expected = os.getenv("PUBLISHING_UI_PASSWORD", "")
    if expected and not hmac.compare_digest(body.password, expected):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    response.set_cookie(
        "studio_session", _auth_cookie(expected or secrets.token_urlsafe(32)),
        httponly=True, secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax", max_age=12 * 60 * 60, path="/",
    )
    return {"authenticated": True}


@app.post("/api/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("studio_session", path="/")
    return {"authenticated": False}


@app.get("/api/blogs")
def blogs() -> list[dict[str, Any]]:
    try:
        return [
            {**item, "content": normalize_markdown_math(item.get("content", ""))}
            for item in list_blog_history()
        ]
    except Exception:
        logger.exception("blog_history_unavailable")
        raise HTTPException(status_code=503, detail="Blog history is temporarily unavailable.") from None


@app.get("/api/blogs/{workflow_id}")
def blog(workflow_id: str) -> dict[str, Any]:
    for item in list_blog_history():
        if item["thread_id"] == workflow_id:
            return {**item, "content": normalize_markdown_math(item.get("content", ""))}
    raise HTTPException(status_code=404, detail="Article not found.")


@app.delete("/api/blogs/{workflow_id}", dependencies=[Depends(require_publishing_auth)])
def remove_blog(workflow_id: str) -> dict[str, bool]:
    if not delete_blog_history(workflow_id):
        raise HTTPException(status_code=404, detail="Article not found.")
    return {"deleted": True}


@app.post("/api/workflows", status_code=202)
def create_workflow(body: BlogRequest) -> dict[str, str]:
    workflow_id = str(uuid.uuid4())
    editorial_brief = (
        f"{body.topic.strip()}\n\nEditorial brief: Write for {body.audience.strip() or 'general readers'}. "
        f"Use a {body.tone.strip() or 'clear and conversational'} tone. Target {body.length.strip() or 'about 1,000 words'}. "
        "Keep the format natural to the topic; do not force a technical format."
    )
    initial = {
        "topic": editorial_brief, "mode": "", "needs_research": False,
        "queries": [], "evidence": [], "plan": None, "sections": [], "final": "",
        "workflow_id": workflow_id,
    }
    _set_job(workflow_id, status="queued", topic=body.topic.strip())
    executor.submit(_run_workflow, workflow_id, initial, None)
    return {"workflow_id": workflow_id, "status": "queued"}


@app.get("/api/workflows")
def active_workflows() -> list[dict[str, Any]]:
    with jobs_lock:
        records = [dict(item) for item in jobs.values() if item.get("status") not in {"completed", "failed"}]
    return sorted(records, key=lambda item: item.get("updated_at", 0), reverse=True)


@app.get("/api/workflows/{workflow_id}")
def get_workflow(workflow_id: str) -> dict[str, Any]:
    return _workflow_status(workflow_id)


@app.post("/api/workflows/{workflow_id}/actions", dependencies=[Depends(require_publishing_auth)])
def workflow_action(workflow_id: str, body: ActionRequest) -> dict[str, str]:
    state = _workflow_status(workflow_id)
    pending = state.get("pending")
    if not pending:
        raise HTTPException(status_code=409, detail="This workflow has no pending approval.")
    if pending.get("type") == "blog_review":
        if body.action == "approve":
            resume = {"action": "approve", "platforms": body.platforms}
        elif body.action == "edit":
            if body.content is None:
                raise HTTPException(status_code=422, detail="Article content is required for an edit.")
            current_blog = pending.get("blog") or {}
            resume = {"action": "edit", "blog": {**current_blog, "title": body.title or current_blog.get("title", ""), "content": body.content}}
        else:
            resume = {"action": "reject", "feedback": body.feedback}
    elif pending.get("type") == "linkedin_approval":
        resume = {"action": body.action, "text": body.text or (pending.get("draft") or {}).get("text", "")}
    else:
        raise HTTPException(status_code=409, detail="Unknown workflow approval type.")
    _set_job(workflow_id, status="queued", node="human_approval", error=None)
    executor.submit(_run_workflow, workflow_id, None, resume)
    return {"workflow_id": workflow_id, "status": "queued"}


@app.get("/api/publishing")
def publishing_status() -> dict[str, Any]:
    tokens: dict[str, dict[str, Any]] = {}
    publications: list[dict[str, Any]] = []
    published_count = 0
    try:
        with closing(sqlite3.connect(str(database_path()))) as db, db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "oauth_tokens" in tables:
                columns = {row[1] for row in db.execute("PRAGMA table_info(oauth_tokens)")}
                fields = ["account", "expires_at"]
                if "site_url" in columns:
                    fields.append("site_url")
                for row in db.execute(f"SELECT {', '.join(fields)} FROM oauth_tokens"):
                    tokens[row[0]] = {"expires_at": row[1], "site_url": row[2] if len(row) > 2 else ""}
            if "publications" in tables:
                published_count = db.execute(
                    "SELECT COUNT(*) FROM publications WHERE status='published'"
                ).fetchone()[0]
                for platform, status, url, updated_at in db.execute(
                    "SELECT platform,status,url,updated_at FROM publications ORDER BY updated_at DESC LIMIT 30"
                ):
                    publications.append({"platform": platform, "status": status, "url": url, "updated_at": updated_at})
    except sqlite3.Error:
        logger.exception("publishing_status_unavailable")
    now = time.time()
    wordpress_token = tokens.get("wordpress")
    linkedin_token = tokens.get("linkedin")
    destinations = {
        "wordpress": {
            "name": "WordPress.com", "connected": bool(wordpress_token and (not wordpress_token["expires_at"] or wordpress_token["expires_at"] > now)),
            "configured": bool(os.getenv("WORDPRESS_CLIENT_ID") and os.getenv("WORDPRESS_CLIENT_SECRET")),
            "connect_url": "/auth/linkedin/wordpress/connect", "site_url": wordpress_token.get("site_url", "") if wordpress_token else "",
        },
        "devto": {"name": "DEV.to", "connected": bool(os.getenv("DEV_API_KEY")), "configured": bool(os.getenv("DEV_API_KEY"))},
        "linkedin": {
            "name": "LinkedIn", "connected": bool(linkedin_token and linkedin_token["expires_at"] > now),
            "configured": bool(os.getenv("LINKEDIN_CLIENT_ID") and os.getenv("LINKEDIN_CLIENT_SECRET")),
            "connect_url": "/auth/linkedin/connect",
        },
    }
    return {
        "destinations": destinations,
        "publications": publications,
        "published_count": published_count,
    }


@app.post("/api/publishing/{platform}/connect", dependencies=[Depends(require_publishing_auth)])
def publishing_connect(platform: Literal["wordpress", "linkedin"]) -> dict[str, str]:
    destinations = publishing_status()["destinations"]
    destination = destinations[platform]
    if not destination.get("configured"):
        raise HTTPException(status_code=503, detail=f"{destination['name']} OAuth is not configured.")
    return {"url": destination["connect_url"]}


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        requested = frontend_dist / path
        if path and requested.is_file() and frontend_dist in requested.resolve().parents:
            return FileResponse(requested)
        return FileResponse(frontend_dist / "index.html")
