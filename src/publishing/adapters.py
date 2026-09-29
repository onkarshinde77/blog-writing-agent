"""Small server-side adapters for official publishing APIs."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests
import bleach

log = logging.getLogger(__name__)
TIMEOUT = 25


def _request(method: str, url: str, *, headers=None, json_body=None) -> requests.Response:
    """Retry transient errors only; never log request headers or response bodies."""
    for attempt in range(4):
        try:
            response = requests.request(method, url, headers=headers, json=json_body, timeout=TIMEOUT)
        except requests.RequestException as exc:
            if attempt == 3:
                log.error("api_request_failed host=%s retry_count=%d classification=network_error", urlparse(url).hostname, attempt)
                raise RuntimeError("network_error") from exc
            log.warning("api_request_retry host=%s retry_count=%d classification=network_error", urlparse(url).hostname, attempt + 1)
            time.sleep(2**attempt)
            continue
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 3:
                log.error("api_request_failed host=%s retry_count=%d classification=http_%d", urlparse(url).hostname, attempt, response.status_code)
                raise RuntimeError(f"http_{response.status_code}")
            log.warning("api_request_retry host=%s retry_count=%d classification=http_%d", urlparse(url).hostname, attempt + 1, response.status_code)
            retry_after = response.headers.get("Retry-After")
            time.sleep(min(float(retry_after), 30) if retry_after and retry_after.isdigit() else 2**attempt)
            continue
        if not response.ok:
            raise RuntimeError(f"http_{response.status_code}")
        return response
    raise RuntimeError("request_failed")


def _safe_url(value: str) -> str:
    parsed = urlparse(value or "")
    if parsed.scheme not in {"https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("URLs must be absolute HTTPS URLs without embedded credentials")
    return value


def _meta(blog: dict) -> dict:
    # Keep Markdown syntax while escaping raw HTML and dangerous Markdown URL schemes.
    text = bleach.clean(str(blog["content"]), tags=[], attributes={}, protocols=["http", "https", "mailto"], strip=False)
    text = __import__("re").sub(r"\]\(\s*(?:javascript|data|vbscript):[^)]*\)", "]()", text, flags=__import__("re").I)
    return {"title": str(blog["title"])[:200], "content": text, "description": str(blog.get("description", ""))[:300],
            "tags": [str(t)[:30] for t in blog.get("tags", [])[:5]], "cover_image": blog.get("cover_image"),
            "canonical_url": blog.get("canonical_url") or os.getenv("CANONICAL_URL")}


def _idempotency_db() -> str:
    return os.getenv("PUBLISHING_DB_PATH", "publishing.db")


def _init_db():
    with sqlite3.connect(_idempotency_db(), timeout=10) as db:
        db.execute("CREATE TABLE IF NOT EXISTS publications (workflow_id TEXT, content_hash TEXT, platform TEXT, status TEXT, post_id TEXT, url TEXT, updated_at TEXT, PRIMARY KEY(workflow_id, platform))")


def _publish_once(platform: str, workflow_id: str, blog: dict, publish_fn) -> dict:
    data = _meta(blog)
    digest = hashlib.sha256((data["title"] + "\n" + data["content"]).encode()).hexdigest()
    _init_db()
    with sqlite3.connect(_idempotency_db(), timeout=10) as db:
        row = db.execute("SELECT content_hash,status,post_id,url FROM publications WHERE workflow_id=? AND platform=?", (workflow_id, platform)).fetchone()
        if row and row[0] == digest and row[1] == "published":
            return {"platform": platform, "status": row[1], "post_id": row[2], "url": row[3], "error": None}
        db.execute("INSERT OR REPLACE INTO publications VALUES (?,?,?,?,?,?,?)", (workflow_id, digest, platform, "publishing", None, None, datetime.now(timezone.utc).isoformat()))
    try:
        post_id, url = publish_fn(data)
        result = {"platform": platform, "status": "published", "post_id": str(post_id or ""), "url": _safe_url(url), "error": None}
    except Exception as exc:
        # Keep returned error classifications concise and free of raw API payloads/secrets.
        result = {"platform": platform, "status": "failed", "post_id": None, "url": None, "error": str(exc)[:120]}
    with sqlite3.connect(_idempotency_db(), timeout=10) as db:
        db.execute("INSERT OR REPLACE INTO publications VALUES (?,?,?,?,?,?,?)", (workflow_id, digest, platform, result["status"], result["post_id"], result["url"], datetime.now(timezone.utc).isoformat()))
    log.info("publish_result workflow_id=%s platform=%s status=%s post_id=%s error=%s", workflow_id, platform, result["status"], result["post_id"], result["error"])
    return result


def publish_hashnode(blog: dict, workflow_id: str) -> dict:
    def send(data):
        token, publication = os.getenv("HASHNODE_API_TOKEN"), os.getenv("HASHNODE_PUBLICATION_ID")
        if not token or not publication: raise RuntimeError("missing_credentials")
        query = "mutation PublishPost($input: PublishPostInput!) { publishPost(input: $input) { post { id url } } }"
        inp: dict[str, Any] = {"publicationId": publication, "title": data["title"], "contentMarkdown": data["content"], "tags": [{"slug": t.lower().replace(" ", "-")} for t in data["tags"]]}
        if data["description"]: inp["subtitle"] = data["description"]
        if data["cover_image"]: inp["coverImageOptions"] = {"coverImageURL": _safe_url(data["cover_image"])}
        if data["canonical_url"]: inp["originalArticleURL"] = _safe_url(data["canonical_url"])
        payload = _request("POST", "https://gql.hashnode.com", headers={"Authorization": token}, json_body={"query": query, "variables": {"input": inp}}).json()
        if payload.get("errors"): raise RuntimeError("graphql_error")
        post = payload.get("data", {}).get("publishPost", {}).get("post") or {}
        if not post.get("url"): raise RuntimeError("invalid_api_response")
        return post.get("id"), post["url"]
    return _publish_once("hashnode", workflow_id, blog, send)


def publish_devto(blog: dict, workflow_id: str) -> dict:
    def send(data):
        key = os.getenv("DEV_API_KEY")
        if not key: raise RuntimeError("missing_credentials")
        article = {"title": data["title"], "body_markdown": data["content"], "published": True, "description": data["description"] or None, "tags": ", ".join(data["tags"][:4])}
        if data["cover_image"]: article["main_image"] = _safe_url(data["cover_image"])
        if data["canonical_url"]: article["canonical_url"] = _safe_url(data["canonical_url"])
        payload = _request("POST", "https://dev.to/api/articles", headers={"api-key": key}, json_body={"article": article}).json()
        if not payload.get("url"): raise RuntimeError("invalid_api_response")
        return payload.get("id"), payload["url"]
    return _publish_once("devto", workflow_id, blog, send)


def _ghost_token(key: str) -> str:
    import jwt
    kid, secret = key.split(":", 1)
    now = int(time.time())
    return jwt.encode({"iat": now, "exp": now + 300, "aud": "/admin/"}, bytes.fromhex(secret), algorithm="HS256", headers={"kid": kid})


def publish_ghost(blog: dict, workflow_id: str) -> dict:
    def send(data):
        base, key = os.getenv("GHOST_URL", "").rstrip("/"), os.getenv("GHOST_ADMIN_API_KEY", "")
        if not base or not key: raise RuntimeError("missing_credentials")
        _safe_url(base)
        from markdown import markdown
        html = markdown(data["content"], extensions=["tables", "fenced_code"])
        html = bleach.clean(html, tags={"p", "br", "h1", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "pre", "code", "strong", "em", "del", "a", "hr", "table", "thead", "tbody", "tr", "th", "td"}, attributes={"a": ["href", "title"]}, protocols=["http", "https", "mailto"], strip=True)
        post = {"title": data["title"], "html": html, "status": "published" if os.getenv("GHOST_PUBLISH_STATUS", "published").lower() == "published" else "draft"}
        if data["description"]: post["custom_excerpt"] = data["description"]
        if data["cover_image"]: post["feature_image"] = _safe_url(data["cover_image"])
        if data["canonical_url"]: post["canonical_url"] = _safe_url(data["canonical_url"])
        url = f"{base}/ghost/api/admin/posts/?source=html"
        payload = _request("POST", url, headers={"Authorization": f"Ghost {_ghost_token(key)}", "Accept-Version": "v5.0"}, json_body={"posts": [post]}).json()
        created = payload.get("posts", [{}])[0]
        if not created.get("url"): raise RuntimeError("invalid_api_response")
        return created.get("id"), created["url"]
    return _publish_once("ghost", workflow_id, blog, send)


def publish_linkedin(text: str, author: str | None = None, workflow_id: str | None = None) -> dict:
    try:
        from src.publishing.linkedin_oauth import get_linkedin_token, get_linkedin_author
        token = get_linkedin_token() or os.getenv("LINKEDIN_ACCESS_TOKEN")
        author = author or get_linkedin_author()
    except Exception:
        token, author = os.getenv("LINKEDIN_ACCESS_TOKEN"), author or os.getenv("LINKEDIN_AUTHOR_URN")
    if not token or not author: return {"platform": "linkedin", "status": "failed", "post_id": None, "url": None, "error": "missing_credentials"}
    if not author.startswith("urn:li:person:"): return {"platform": "linkedin", "status": "failed", "post_id": None, "url": None, "error": "member_author_urn_required"}
    version = os.getenv("LINKEDIN_API_VERSION", "202608")
    def send(data):
        response = _request("POST", "https://api.linkedin.com/rest/posts", headers={"Authorization": f"Bearer {token}", "LinkedIn-Version": version, "X-Restli-Protocol-Version": "2.0.0"}, json_body={"author": author, "commentary": data["content"], "visibility": "PUBLIC", "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []}, "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False})
        post_id = response.headers.get("x-restli-id", "")
        if not post_id: raise RuntimeError("invalid_api_response")
        return post_id, "https://www.linkedin.com/feed/update/" + post_id
    if workflow_id:
        result = _publish_once("linkedin", workflow_id, {"title": "LinkedIn post", "content": text}, send)
        result["platform"] = "linkedin"
        return result
    try:
        post_id, url = send({"content": text})
        return {"platform": "linkedin", "status": "published", "post_id": post_id, "url": url, "error": None}
    except Exception as exc:
        return {"platform": "linkedin", "status": "failed", "post_id": None, "url": None, "error": str(exc)[:120]}
