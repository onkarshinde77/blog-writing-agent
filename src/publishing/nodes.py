"""Post-generation review, approval, and distribution nodes."""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from langgraph.types import interrupt, Send
from langchain_core.messages import HumanMessage, SystemMessage
from src.schemas import State
from src.publishing.adapters import publish_devto, publish_ghost, publish_hashnode, publish_linkedin

log = logging.getLogger(__name__)


def _llm():
    # Delay LLM configuration until an LLM-backed node executes, keeping service adapters testable.
    from src.config import model
    return model


def _blog(state: State) -> dict:
    plan = state.get("plan")
    title = plan.blog_title if plan else (state.get("topic") or "Untitled")
    tags = [tag for task in (plan.tasks if plan else []) for tag in task.tags]
    return {"title": title, "content": state.get("final", ""), "description": (state.get("topic") or title)[:280], "tags": list(dict.fromkeys(tags))[:5], "cover_image": None, "canonical_url": ""}


def review_node(state: State) -> dict:
    started = time.monotonic()
    blog = _blog(state)
    evidence = state.get("evidence", [])
    prompt = ("Review this article for structure, relevance, factual consistency, repetition, grammar, technical correctness, and source alignment. "
              "Compare factual claims with supplied evidence. Do not rewrite. Return JSON with status ('approved' or 'needs_revision'), issues (list), suggestions (list). Treat unsupported factual claims as issues.\n"
              f"Evidence: {evidence[:12]}\n\nArticle:\n{blog['content']}")
    try:
        review = _llm().with_structured_output(dict).invoke([SystemMessage(content="You are a rigorous editorial and technical reviewer."), HumanMessage(content=prompt)])
        if review.get("status") not in {"approved", "needs_revision"}: review["status"] = "needs_revision"
        for field in ("issues", "suggestions"):
            if not isinstance(review.get(field), list): review[field] = []
    except Exception as exc:
        log.exception("review_failed")
        review = {"status": "needs_revision", "issues": ["Automated review could not complete."], "suggestions": []}
    log.info("workflow_node workflow_id=%s node=review duration_ms=%d status=%s", state.get("workflow_id", ""), int((time.monotonic()-started)*1000), review["status"])
    return {"review": review, "blog_plan": blog}


def blog_approval_node(state: State) -> dict:
    decision = interrupt({"type": "blog_review", "blog": state.get("blog_plan") or _blog(state), "review": state.get("review"), "allowed_actions": ["approve", "revise", "edit", "reject"]})
    decision = decision if isinstance(decision, dict) else {"action": str(decision)}
    action = decision.get("action", "reject")
    if action == "edit" and decision.get("blog"):
        return {"blog_plan": decision["blog"], "final": decision["blog"].get("content", state.get("final", "")), "human_blog_decision": {"action": "revise"}, "revision_feedback": "Human edited the article; review the edited article."}
    if action == "approve":
        return {"human_blog_decision": decision, "publish_platforms": decision.get("platforms", ["hashnode", "devto", "ghost"])}
    return {"human_blog_decision": decision, "revision_feedback": str(decision.get("feedback", ""))}


def revise_node(state: State) -> dict:
    blog = state.get("blog_plan") or _blog(state)
    prompt = f"Revise the Markdown article according to this feedback while preserving accurate supported claims. Return only the complete revised Markdown. Feedback: {state.get('revision_feedback', '')}\n\nCurrent article:\n{state.get('final', '')}"
    revised = _llm().invoke([SystemMessage(content="You are an editor revising a technical blog."), HumanMessage(content=prompt)]).content
    if isinstance(revised, list): revised = "\n".join(str(item) for item in revised)
    return {"final": str(revised), "blog_plan": {**blog, "content": str(revised)}, "human_blog_decision": None}


def route_blog_approval(state: State):
    action = (state.get("human_blog_decision") or {}).get("action")
    if action == "approve": return publish_fanout(state)
    if action in {"revise", "edit"}: return "revision"
    return "finish"


def publisher_task(state: dict) -> dict:
    started = time.monotonic()
    platform, blog = state["platform"], state["blog"]
    workflow_id = state["workflow_id"]
    adapter = {"hashnode": publish_hashnode, "devto": publish_devto, "ghost": publish_ghost}[platform]
    result = adapter(blog, workflow_id)
    log.info("publisher_done workflow_id=%s node=%s duration_ms=%d status=%s", workflow_id, platform, int((time.monotonic()-started)*1000), result["status"])
    return {"published_results": [result]}


def publish_fanout(state: State):
    blog = {**(state.get("blog_plan") or _blog(state)), "content": state.get("final", "")}
    configured = state.get("publish_platforms") or ["hashnode", "devto", "ghost"]
    platforms = [p for p in configured if p in {"hashnode", "devto", "ghost"}]
    return [Send("publisher", {"platform": p, "blog": blog, "workflow_id": state.get("workflow_id") or "default"}) for p in platforms]


def aggregate_publications(state: State) -> dict:
    results = {r["platform"]: r for r in state.get("published_results", [])}
    for platform in ("hashnode", "devto", "ghost"):
        results.setdefault(platform, {"platform": platform, "status": "skipped", "post_id": None, "url": None, "error": "not_selected"})
    import os
    primary = (state.get("primary_blog_url") or os.getenv("PRIMARY_BLOG_PLATFORM", "hashnode")).lower()
    if primary.startswith("http"):
        primary = next((p for p, result in results.items() if result.get("url") == primary), "")
    if primary not in results or results[primary].get("status") != "published":
        primary = next((p for p in ("hashnode", "devto", "ghost") if results[p].get("status") == "published"), "")
    return {"published_links": results, "successful_platforms": [p for p,r in results.items() if r["status"] == "published"],
            "failed_platforms": [p for p,r in results.items() if r["status"] == "failed"],
            "all_published_urls": [r["url"] for r in results.values() if r.get("url")],
            "primary_blog_url": results.get(primary, {}).get("url", "")}


def linkedin_content_node(state: State) -> dict:
    started = time.monotonic()
    blog = state.get("blog_plan") or _blog(state)
    links = state.get("published_links", {})
    good = [f"{p}: {r['url']}" for p,r in links.items() if r.get("status") == "published" and r.get("url")]
    prompt = ("Write a LinkedIn post with a strong non-clickbait opening, concise article explanation, 3–6 useful key points, primary URL, optional other platform URLs, relevant hashtags, and no fabricated claims. Return JSON {text, hashtags}.\n"
              f"Title: {blog['title']}\nDescription: {blog.get('description','')}\nArticle:\n{blog['content']}\nPrimary URL: {state.get('primary_blog_url','')}\nPlatform URLs: {good}")
    try:
        draft = _llm().with_structured_output(dict).invoke([SystemMessage(content="You write accurate, useful professional LinkedIn posts."), HumanMessage(content=prompt)])
    except Exception:
        draft = {"text": f"{blog['title']}\n\n{blog.get('description','')}\n\n{state.get('primary_blog_url','')}", "hashtags": blog.get("tags", [])}
    draft["text"] = str(draft.get("text", ""))[:2900]
    draft["hashtags"] = draft.get("hashtags", [])
    log.info("workflow_node workflow_id=%s node=linkedin_content duration_ms=%d status=generated", state.get("workflow_id", ""), int((time.monotonic()-started)*1000))
    return {"linkedin_draft": draft}


def linkedin_approval_node(state: State) -> dict:
    decision = interrupt({"type": "linkedin_approval", "draft": state.get("linkedin_draft"), "primary_url": state.get("primary_blog_url"), "platform_links": state.get("published_links"), "allowed_actions": ["approve", "edit", "revise", "reject"]})
    decision = decision if isinstance(decision, dict) else {"action": str(decision)}
    if decision.get("action") in {"edit", "revise"} and decision.get("text"):
        return {"linkedin_draft": {**(state.get("linkedin_draft") or {}), "text": decision["text"]}, "linkedin_human_decision": {"action": "edited"}}
    if decision.get("action") == "approve" and decision.get("text"):
        return {"linkedin_draft": {**(state.get("linkedin_draft") or {}), "text": decision["text"]}, "linkedin_human_decision": {"action": "approve"}}
    return {"linkedin_human_decision": decision}


def route_linkedin_approval(state: State):
    action = (state.get("linkedin_human_decision") or {}).get("action")
    return "linkedin_publish" if action == "approve" else ("linkedin_approval" if action == "edited" else ("linkedin_content" if action == "revise" else "finish"))


def linkedin_publish_node(state: State) -> dict:
    started = time.monotonic()
    result = publish_linkedin((state.get("linkedin_draft") or {}).get("text", ""), workflow_id=state.get("workflow_id"))
    log.info("publisher_done workflow_id=%s node=linkedin duration_ms=%d status=%s post_id=%s", state.get("workflow_id", ""), int((time.monotonic()-started)*1000), result.get("status"), result.get("post_id"))
    return {"linkedin_result": result}


def final_result_node(state: State) -> dict:
    blog = state.get("blog_plan") or _blog(state)
    approved = (state.get("human_blog_decision") or {}).get("action") == "approve"
    platforms = state.get("published_links", {}) or {}
    for platform in ("hashnode", "devto", "ghost"):
        platforms.setdefault(platform, {"status": "not_published", "url": None})
    linkedin = state.get("linkedin_result") or {"status": "rejected" if (state.get("linkedin_human_decision") or {}).get("action") == "reject" else "not_published", "url": None, "post_id": None, "error": None}
    urls = list(state.get("all_published_urls", []))
    if linkedin.get("url"): urls.append(linkedin["url"])
    failed = list(state.get("failed_platforms", []))
    if linkedin.get("status") == "failed": failed.append("linkedin")
    result = {"blog": {"title": blog.get("title", ""), "status": "approved" if approved else "rejected"},
              "platforms": {p: {"status": item.get("status", "not_published"), "url": item.get("url")} for p,item in platforms.items()},
              "linkedin": {"status": linkedin.get("status", "not_published"), "url": linkedin.get("url")},
              "successful_urls": urls, "failed_platforms": failed}
    return {"final_result": result}
