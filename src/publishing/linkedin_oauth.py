"""Minimal backend LinkedIn OAuth endpoints. Mount router in the authenticated web service."""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth/linkedin", tags=["linkedin-oauth"])
_basic = HTTPBasic()
DB_PATH = os.getenv("PUBLISHING_DB_PATH", "publishing.db")


def _require_auth(credentials: HTTPBasicCredentials = Depends(_basic)):
    username, password = os.getenv("PUBLISHING_WEB_USER", ""), os.getenv("PUBLISHING_WEB_PASSWORD", "")
    if not username or not password or not secrets.compare_digest(credentials.username, username) or not secrets.compare_digest(credentials.password, password):
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Basic"})


def _fernet():
    key = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not key: raise RuntimeError("TOKEN_ENCRYPTION_KEY must be set for LinkedIn OAuth")
    return Fernet(key.encode())


def _db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("CREATE TABLE IF NOT EXISTS oauth_states (state_hash TEXT PRIMARY KEY, created REAL NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS oauth_tokens (account TEXT PRIMARY KEY, token_ciphertext BLOB NOT NULL, expires_at REAL NOT NULL, refresh_ciphertext BLOB, author_urn TEXT)")
        columns = {row[1] for row in db.execute("PRAGMA table_info(oauth_tokens)")}
        if "author_urn" not in columns: db.execute("ALTER TABLE oauth_tokens ADD COLUMN author_urn TEXT")
        if "site_id" not in columns: db.execute("ALTER TABLE oauth_tokens ADD COLUMN site_id TEXT")
        if "site_url" not in columns: db.execute("ALTER TABLE oauth_tokens ADD COLUMN site_url TEXT")


@router.get("/connect", dependencies=[Depends(_require_auth)])
def linkedin_connect():
    required = ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "LINKEDIN_REDIRECT_URI")
    if any(not os.getenv(k) for k in required): raise HTTPException(503, "LinkedIn OAuth is not configured")
    _db()
    state = secrets.token_urlsafe(32)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT INTO oauth_states VALUES (?,?)", (hashlib.sha256(state.encode()).hexdigest(), time.time()))
    params = {"response_type": "code", "client_id": os.environ["LINKEDIN_CLIENT_ID"], "redirect_uri": os.environ["LINKEDIN_REDIRECT_URI"], "state": state, "scope": "openid profile w_member_social"}
    return RedirectResponse("https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params))


@router.get("/callback", dependencies=[Depends(_require_auth)])
def linkedin_callback(request: Request, code: str, state: str):
    _db()
    digest = hashlib.sha256(state.encode()).hexdigest()
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT created FROM oauth_states WHERE state_hash=?", (digest,)).fetchone()
        db.execute("DELETE FROM oauth_states WHERE state_hash=?", (digest,))
    if not row or time.time() - row[0] > 600: raise HTTPException(400, "Invalid or expired OAuth state")
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": os.environ["LINKEDIN_REDIRECT_URI"], "client_id": os.environ["LINKEDIN_CLIENT_ID"], "client_secret": os.environ["LINKEDIN_CLIENT_SECRET"]}
    response = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data=data, timeout=20)
    if not response.ok: raise HTTPException(502, "LinkedIn token exchange failed")
    token = response.json()
    profile = requests.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": "Bearer " + token["access_token"]}, timeout=20)
    if not profile.ok: raise HTTPException(502, "Could not obtain LinkedIn member identity")
    subject = profile.json().get("sub")
    if not subject: raise HTTPException(502, "LinkedIn member identity was not returned")
    f = _fernet()
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT OR REPLACE INTO oauth_tokens VALUES (?,?,?,?,?)", ("linkedin", f.encrypt(token["access_token"].encode()), time.time()+int(token.get("expires_in", 0)), f.encrypt(token["refresh_token"].encode()) if token.get("refresh_token") else None, f"urn:li:person:{subject}"))
    # Author URN is returned to the backend session; token itself is never returned to a browser.
    return {"connected": True, "author_urn": f"urn:li:person:{subject}"}


@router.get("/wordpress/connect", dependencies=[Depends(_require_auth)])
def wordpress_connect():
    required = ("WORDPRESS_CLIENT_ID", "WORDPRESS_CLIENT_SECRET", "WORDPRESS_REDIRECT_URI")
    if any(not os.getenv(k) for k in required): raise HTTPException(503, "WordPress.com OAuth is not configured")
    site = os.getenv("WORDPRESS_SITE_ID") or os.getenv("WORDPRESS_SITE_URL")
    if not site: raise HTTPException(503, "Set WORDPRESS_SITE_ID or WORDPRESS_SITE_URL")
    _db()
    state = secrets.token_urlsafe(32)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT INTO oauth_states VALUES (?,?)", (hashlib.sha256(state.encode()).hexdigest(), time.time()))
    params = {"client_id": os.environ["WORDPRESS_CLIENT_ID"], "redirect_uri": os.environ["WORDPRESS_REDIRECT_URI"], "response_type": "code", "scope": "posts media", "blog": site, "state": state}
    return RedirectResponse("https://public-api.wordpress.com/oauth2/authorize?" + urlencode(params))


@router.get("/wordpress/callback", dependencies=[Depends(_require_auth)])
def wordpress_callback(code: str, state: str):
    _db()
    digest = hashlib.sha256(state.encode()).hexdigest()
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT created FROM oauth_states WHERE state_hash=?", (digest,)).fetchone()
        db.execute("DELETE FROM oauth_states WHERE state_hash=?", (digest,))
    if not row or time.time() - row[0] > 600: raise HTTPException(400, "Invalid or expired OAuth state")
    data = {"client_id": os.environ["WORDPRESS_CLIENT_ID"], "client_secret": os.environ["WORDPRESS_CLIENT_SECRET"], "code": code, "grant_type": "authorization_code", "redirect_uri": os.environ["WORDPRESS_REDIRECT_URI"]}
    response = requests.post("https://public-api.wordpress.com/oauth2/token", data=data, timeout=20)
    if not response.ok: raise HTTPException(502, "WordPress.com token exchange failed")
    token = response.json()
    if not token.get("access_token"): raise HTTPException(502, "WordPress.com did not return an access token")
    f = _fernet()
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT OR REPLACE INTO oauth_tokens (account,token_ciphertext,expires_at,refresh_ciphertext,author_urn,site_id,site_url) VALUES (?,?,?,?,?,?,?)", ("wordpress", f.encrypt(token["access_token"].encode()), time.time()+int(token.get("expires_in", 0)) if token.get("expires_in") else 0, None, None, str(token.get("blog_id", "")), token.get("blog_url", "")))
    return {"connected": True, "site_id": str(token.get("blog_id", "")), "site_url": token.get("blog_url", "")}


def get_linkedin_token() -> str | None:
    """Read the encrypted OAuth token for server-side API calls."""
    _db()
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT token_ciphertext, expires_at, refresh_ciphertext FROM oauth_tokens WHERE account='linkedin'").fetchone()
    if not row: return None
    f = _fernet()
    if row[1] <= time.time() + 90:
        if not row[2] or not os.getenv("LINKEDIN_CLIENT_ID") or not os.getenv("LINKEDIN_CLIENT_SECRET"): return None
        refresh_token = f.decrypt(row[2]).decode()
        response = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data={"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": os.environ["LINKEDIN_CLIENT_ID"], "client_secret": os.environ["LINKEDIN_CLIENT_SECRET"]}, timeout=20)
        if not response.ok: return None
        tokens = response.json()
        if not tokens.get("access_token"): return None
        new_refresh = tokens.get("refresh_token", refresh_token)
        with sqlite3.connect(DB_PATH) as db:
            db.execute("UPDATE oauth_tokens SET token_ciphertext=?,expires_at=?,refresh_ciphertext=? WHERE account='linkedin'", (f.encrypt(tokens["access_token"].encode()), time.time()+int(tokens.get("expires_in", 0)), f.encrypt(new_refresh.encode())))
        return tokens["access_token"]
    return f.decrypt(row[0]).decode()


def get_linkedin_author() -> str | None:
    _db()
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT author_urn FROM oauth_tokens WHERE account='linkedin'").fetchone()
    return row[0] if row else os.getenv("LINKEDIN_AUTHOR_URN")


def get_wordpress_token() -> str | None:
    _db()
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT token_ciphertext,expires_at FROM oauth_tokens WHERE account='wordpress'").fetchone()
    if not row or (row[1] and row[1] <= time.time()): return None
    return _fernet().decrypt(row[0]).decode()


def get_wordpress_site_id() -> str | None:
    _db()
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT site_id FROM oauth_tokens WHERE account='wordpress'").fetchone()
    return (row[0] if row else None) or os.getenv("WORDPRESS_SITE_ID")
