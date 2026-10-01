import hashlib, hmac, os, time
from fastapi import Cookie, HTTPException

def _auth_cookie(password: str) -> str:
    expires = str(int(time.time()) + 12 * 60 * 60)
    signature = hmac.new(password.encode(), expires.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


# Check whether a dashboard session cookie is valid.

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


# Protect review and publishing endpoints when a password is configured.

def require_publishing_auth(studio_session: str | None = Cookie(default=None)) -> None:
    if not _is_authenticated(studio_session):
        raise HTTPException(status_code=401, detail="Sign in to manage reviews and publishing.")


# Convert LangGraph and Pydantic values into JSON-friendly Python data.

