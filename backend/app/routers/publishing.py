import logging, os, sqlite3, time
from contextlib import closing
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException
from src.blog_history import database_path
from ..security import require_publishing_auth
logger=logging.getLogger("editorial_studio")
router=APIRouter()

@router.get("/api/publishing")
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
                    publications.append(
                        {
                            "platform": platform,
                            "status": status,
                            "url": url,
                            "updated_at": updated_at,
                        }
                    )
    except sqlite3.Error:
        logger.exception("publishing_status_unavailable")
    now = time.time()
    wordpress_token = tokens.get("wordpress")
    linkedin_token = tokens.get("linkedin")
    destinations = {
        "wordpress": {
            "name": "WordPress.com",
            "connected": bool(
                wordpress_token
                and (
                    not wordpress_token["expires_at"]
                    or wordpress_token["expires_at"] > now
                )
            ),
            "configured": bool(
                os.getenv("WORDPRESS_CLIENT_ID")
                and os.getenv("WORDPRESS_CLIENT_SECRET")
            ),
            "connect_url": "/auth/linkedin/wordpress/connect",
            "site_url": wordpress_token.get("site_url", "") if wordpress_token else "",
        },
        "devto": {
            "name": "DEV.to",
            "connected": bool(os.getenv("DEV_API_KEY")),
            "configured": bool(os.getenv("DEV_API_KEY")),
        },
        "linkedin": {
            "name": "LinkedIn",
            "connected": bool(linkedin_token and linkedin_token["expires_at"] > now),
            "configured": bool(
                os.getenv("LINKEDIN_CLIENT_ID")
                and os.getenv("LINKEDIN_CLIENT_SECRET")
            ),
            "connect_url": "/auth/linkedin/connect",
        },
    }
    return {
        "destinations": destinations,
        "publications": publications,
        "published_count": published_count,
    }


# Return the OAuth URL for a configured publishing platform.

@router.post("/api/publishing/{platform}/connect", dependencies=[Depends(require_publishing_auth)])
def publishing_connect(platform: Literal["wordpress", "linkedin"]) -> dict[str, str]:
    destinations = publishing_status()["destinations"]
    destination = destinations[platform]
    if not destination.get("configured"):
        raise HTTPException(status_code=503, detail=f"{destination['name']} OAuth is not configured.")
    return {"url": destination["connect_url"]}
