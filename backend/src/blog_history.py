"""Local SQLite persistence for generated blog history."""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def database_path() -> Path:
    """Resolve the one local database path used throughout the application."""
    path = Path(os.getenv("PUBLISHING_DB_PATH", "publishing.db"))
    if not path.is_absolute():
        # Keep relative database paths rooted at the repository after moving
        # the Python package into backend/.
        path = Path(__file__).resolve().parents[2] / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path()), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def _value(value: Any, field: str, default: Any = "") -> Any:
    if isinstance(value, dict):
        return value.get(field, default)
    return getattr(value, field, default)


def save_blog_history(
    thread_id: str | None,
    topic: str,
    title: str,
    content: str,
    status: str = "generated",
) -> None:
    """Insert or update one blog while preserving its original creation time."""
    if not thread_id:
        raise ValueError("A workflow thread ID is required to save blog history.")
    now = datetime.now(timezone.utc).isoformat()
    with closing(_connect()) as db, db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS blog_history (
                thread_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        db.execute(
            """INSERT INTO blog_history
                (thread_id, topic, title, content, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    topic=excluded.topic,
                    title=excluded.title,
                    content=excluded.content,
                    status=excluded.status,
                    updated_at=excluded.updated_at""",
            (str(thread_id), topic or title, title or topic, content, status, now, now),
        )


def list_blog_history(limit: int = 200) -> list[dict[str, str]]:
    """Return saved blogs newest first, creating the empty table on first use."""
    with closing(_connect()) as db, db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS blog_history (
                thread_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        rows = db.execute(
            """SELECT thread_id, topic, title, content, status, created_at, updated_at
               FROM blog_history ORDER BY created_at DESC LIMIT ?""",
            (max(1, min(int(limit), 1000)),),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_blog_history(thread_id: str) -> bool:
    """Delete a saved article from the library without altering workflow checkpoints."""
    with closing(_connect()) as db, db:
        cursor = db.execute("DELETE FROM blog_history WHERE thread_id = ?", (str(thread_id),))
    return cursor.rowcount > 0


def recover_checkpoint_history(graph: Any) -> int:
    """Backfill older completed blogs from LangGraph checkpoints in this DB."""
    path = database_path()
    with closing(sqlite3.connect(str(path), timeout=10)) as db, db:
        has_checkpoints = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkpoints'"
        ).fetchone()
        if not has_checkpoints:
            return 0
        thread_ids = [row[0] for row in db.execute("SELECT DISTINCT thread_id FROM checkpoints")]

    existing = {blog["thread_id"] for blog in list_blog_history(limit=1000)}
    recovered = 0
    for thread_id in thread_ids:
        if not thread_id or thread_id in existing or thread_id in {"blog-1", "__default__"}:
            continue
        try:
            snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
            values = snapshot.values or {}
            plan = values.get("plan")
            blog = values.get("blog_plan") or {}
            content = values.get("final") or _value(blog, "content")
            if not content:
                continue
            title = _value(blog, "title") or _value(plan, "blog_title") or values.get("topic") or "Recovered blog"
            save_blog_history(
                str(thread_id),
                str(values.get("topic") or title),
                str(title),
                str(content),
                status="recovered",
            )
            recovered += 1
        except Exception:
            # A malformed/old checkpoint must not hide accessible saved history.
            continue
    return recovered


def save_state_blog(state: dict, *, status: str = "generated") -> None:
    """Save the blog fields carried by a LangGraph state update."""
    plan = state.get("plan")
    blog = state.get("blog_plan") or {}
    title = (
        _value(blog, "title")
        or _value(plan, "blog_title")
        or state.get("topic", "Untitled blog")
    )
    content = state.get("final") or _value(blog, "content") or ""
    save_blog_history(
        state.get("workflow_id"),
        str(state.get("topic") or title),
        str(title),
        str(content),
        status=status,
    )
