import hmac, os, secrets
from fastapi import APIRouter, Cookie, HTTPException, Response
from ..schemas import LoginRequest
from ..security import _auth_cookie, _is_authenticated
router=APIRouter()

@router.get("/api/auth/status")
def auth_status(studio_session: str | None = Cookie(default=None)) -> dict[str, bool]:
    return {
        "required": bool(os.getenv("PUBLISHING_UI_PASSWORD")),
        "authenticated": _is_authenticated(studio_session),
    }

@router.post("/api/auth/login")
def login(body: LoginRequest, response: Response) -> dict[str, bool]:
    expected = os.getenv("PUBLISHING_UI_PASSWORD", "")
    if expected and not hmac.compare_digest(body.password, expected):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    response.set_cookie(
        "studio_session",
        _auth_cookie(expected or secrets.token_urlsafe(32)),
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=12 * 60 * 60,
        path="/",
    )
    return {"authenticated": True}


# Sign out and clear the dashboard session cookie.

@router.post("/api/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("studio_session", path="/")
    return {"authenticated": False}


# Return saved blog history with display-ready math notation.

