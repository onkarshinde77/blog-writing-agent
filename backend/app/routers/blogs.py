import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from src.blog_history import delete_blog_history, list_blog_history
from src.markdown_math import normalize_markdown_math
from ..security import require_publishing_auth
logger=logging.getLogger("editorial_studio")
router=APIRouter()

@router.get("/api/blogs")
def blogs() -> list[dict[str, Any]]:
    try:
        return [
            {**item, "content": normalize_markdown_math(item.get("content", ""))}
            for item in list_blog_history()
        ]
    except Exception:
        logger.exception("blog_history_unavailable")
        raise HTTPException(status_code=503, detail="Blog history is temporarily unavailable.") from None


# Return one saved article by its workflow ID.

@router.get("/api/blogs/{workflow_id}")
def blog(workflow_id: str) -> dict[str, Any]:
    for item in list_blog_history():
        if item["thread_id"] == workflow_id:
            return {**item, "content": normalize_markdown_math(item.get("content", ""))}
    raise HTTPException(status_code=404, detail="Article not found.")


# Delete a saved article after checking that it exists.

@router.delete("/api/blogs/{workflow_id}", dependencies=[Depends(require_publishing_auth)])
def remove_blog(workflow_id: str) -> dict[str, bool]:
    if not delete_blog_history(workflow_id):
        raise HTTPException(status_code=404, detail="Article not found.")
    return {"deleted": True}


# Start a new blog-generation workflow in the background.

