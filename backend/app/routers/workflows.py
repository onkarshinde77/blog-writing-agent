import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from ..schemas import ActionRequest, BlogRequest
from ..security import require_publishing_auth
from ..state import executor, jobs, jobs_lock
from ..workflow_service import _run_workflow, _set_job, _workflow_status
router=APIRouter()

@router.post("/api/workflows", status_code=202)
def create_workflow(body: BlogRequest) -> dict[str, str]:
    workflow_id = str(uuid.uuid4())
    editorial_brief = (
        f"{body.topic.strip()}\n\n"
        "Editorial brief: Infer the intended audience from the topic and explain ideas at the right level for those readers. "
        "Choose a natural tone that fits the topic and audience. "
        f"Target {body.length.strip() or 'about 1,000 words'}. "
        "Keep the format natural to the topic; do not force a technical format."
    )
    initial = {
        "topic": editorial_brief,"mode": "","needs_research": False,
        "queries": [],"evidence": [],"plan": None,"sections": [],
        "final": "","workflow_id": workflow_id,"model_name": body.model_name,
    }
    _set_job(workflow_id, status="queued", topic=body.topic.strip(), model_name=body.model_name)
    executor.submit(_run_workflow, workflow_id, initial, None)
    return {"workflow_id": workflow_id, "status": "queued"}


# List workflows that have not completed or failed.

@router.get("/api/workflows")
def active_workflows() -> list[dict[str, Any]]:
    with jobs_lock:
        records = [
            dict(item)
            for item in jobs.values()
            if item.get("status") not in {"completed", "failed"}
        ]
    return sorted(records, key=lambda item: item.get("updated_at", 0), reverse=True)


# Return the current state of one workflow.

@router.get("/api/workflows/{workflow_id}")
def get_workflow(workflow_id: str) -> dict[str, Any]:
    return _workflow_status(workflow_id)


# Apply a human review decision and resume the workflow.

@router.post("/api/workflows/{workflow_id}/actions", dependencies=[Depends(require_publishing_auth)])
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
            resume = {
                "action": "edit",
                "blog": {
                    **current_blog,
                    "title": body.title or current_blog.get("title", ""),
                    "content": body.content,
                },
            }
        else:
            resume = {"action": "reject", "feedback": body.feedback}
    elif pending.get("type") == "linkedin_approval":
        resume = {"action": body.action, "text": body.text or (pending.get("draft") or {}).get("text", "")}
    else:
        raise HTTPException(status_code=409, detail="Unknown workflow approval type.")
    _set_job(workflow_id, status="queued", node="human_approval", error=None)
    executor.submit(_run_workflow, workflow_id, None, resume)
    return {"workflow_id": workflow_id, "status": "queued"}


# Return publishing connection status and recent publication results.

