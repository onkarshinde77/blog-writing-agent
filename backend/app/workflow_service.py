import logging, time
from typing import Any
from fastapi import HTTPException
from langgraph.types import Command
from src.blog_history import list_blog_history, recover_checkpoint_history
from src.config import DEFAULT_MODEL
from src.graph import app as workflow
from src.markdown_math import normalize_markdown_math
from .state import jobs, jobs_lock
logger=logging.getLogger("editorial_studio")

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

# Build the LangGraph configuration for one saved workflow thread.

def _workflow_config(workflow_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": workflow_id}, "run_name": "blog-writing-agent"}


# Extract the workflow fields returned by the API.

def _snapshot_cache(snapshot: Any, pending: dict[str, Any] | None) -> dict[str, Any]:
    values = snapshot.values or {}
    return {
        "topic": values.get("topic", ""),
        "model_name": values.get("model_name", DEFAULT_MODEL),
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


# Update a workflow's in-memory status and record node changes.

def _set_job(workflow_id: str, **updates: Any) -> None:
    with jobs_lock:
        current = jobs.setdefault(
            workflow_id,
            {"workflow_id": workflow_id, "status": "queued", "node": None, "events": []},
        )
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


# Run or resume a workflow in the background and save its latest status.

def _run_workflow(workflow_id: str,initial: dict[str, Any] | None = None,resume: dict[str, Any] | None = None,) -> None:
    _set_job(workflow_id, status="running", node="router" if initial else "review", error=None)
    config = _workflow_config(workflow_id)
    try:
        if initial is not None:
            stream = workflow.stream(initial, config=config)
        else:
            stream = workflow.stream(Command(resume=resume), config=config)
        for update in stream:
            for node_name in update:
                _set_job(workflow_id, status="running", node=node_name)
        snapshot = workflow.get_state(config)
        interrupts = [interrupt.value for task in snapshot.tasks for interrupt in task.interrupts]
        pending = interrupts[0] if interrupts else None
        if pending:
            if pending.get("type") == "linkedin_approval":
                next_status = "awaiting_linkedin_approval"
            else:
                next_status = "awaiting_review"
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
        _set_job(
            workflow_id,
            status="failed",
            node=None,
            error="The workflow failed. Check the backend logs and try again.",
            state_cache=None,
        )


# Return the latest cached or checkpointed state for a workflow.

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
            "model_name": job.get("model_name", DEFAULT_MODEL),
            "final": "",
            "blog": {},
            "evidence": [],
            "quality_report": {},
            "review": {},
            "audience_analysis": {},
            "pending": None,
            "final_result": {},
            "published_links": {},
            "error": job.get("error"),
            "events": job.get("events", []),
        }
    if job.get("state_cache"):
        cached = dict(job["state_cache"])
        pending = cached.get("pending")
        cached.update(
            {
                "workflow_id": workflow_id,
                "status": job.get("status", "completed"),
                "stage": "Human approval" if pending else None,
                "node": None,
                "error": job.get("error"),
                "events": job.get("events", []),
            }
        )
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
    cached = _snapshot_cache(snapshot, pending)
    cached["model_name"] = values.get("model_name", job.get("model_name", DEFAULT_MODEL))
    return {
        **cached,
        "workflow_id": workflow_id,
        "status": status,
        "stage": _STAGE_MAP.get(current_node, "Human approval" if pending else None),
        "node": current_node,
        "events": job.get("events", []),
        "error": job.get("error"),
    }


# Restore workflows that were waiting for approval when the backend restarted.

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
                if pending.get("type") == "linkedin_approval":
                    status, node = "awaiting_linkedin_approval", "linkedin_approval"
                else:
                    status, node = "awaiting_review", "blog_approval"
                _set_job(
                    workflow_id,
                    topic=article.get("topic", ""),
                    status=status,
                    node=node,
                    state_cache=_snapshot_cache(snapshot, pending),
                    error=None,
                )
            except Exception:
                logger.info("pending_approval_skipped workflow_id=%s", article.get("thread_id", ""))
    except Exception:
        logger.exception("pending_approval_recovery_failed")


# Report whether the API is running.
