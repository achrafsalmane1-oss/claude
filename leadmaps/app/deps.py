"""Shared FastAPI dependencies and template plumbing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import services
from app.config import Settings, get_settings
from app.db import get_session
from app.engine import Engine, build_engine
from app.models import Account, ApiKey, User, utcnow
from app.plans import get_plan
from app.security import read_session

templates = Jinja2Templates(directory="app/templates")


def render(name: str, context: dict, status_code: int = 200):
    """Render a template. ``context`` must carry the request under "request"."""
    return templates.TemplateResponse(
        context["request"], name, context, status_code=status_code
    )


class LoginRequired(Exception):
    """Raised by page dependencies when there is no valid session."""

    def __init__(self, next_url: str = "/app") -> None:
        self.next_url = next_url


@dataclass
class Principal:
    """The authenticated caller, from either a session cookie or an API key."""

    user: User | None
    account: Account
    api_key: ApiKey | None = None

    @property
    def email(self) -> str:
        return self.user.email if self.user else ""

    @property
    def plan(self):
        return get_plan(self.account.plan_code)


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]


def get_engine(settings: SettingsDep) -> Engine:
    return build_engine(settings)


EngineDep = Annotated[Engine, Depends(get_engine)]


def current_user_optional(
    request: Request, session: SessionDep, settings: SettingsDep
) -> User | None:
    token = request.cookies.get(settings.session_cookie)
    if not token:
        return None
    user_id = read_session(token)
    if not user_id:
        return None
    return session.get(User, user_id)


OptionalUserDep = Annotated[User | None, Depends(current_user_optional)]


def require_user(request: Request, user: OptionalUserDep) -> Principal:
    """Dependency for dashboard pages; redirects to login when signed out."""
    if user is None:
        raise LoginRequired(next_url=str(request.url.path))
    return Principal(user=user, account=user.account)


PrincipalDep = Annotated[Principal, Depends(require_user)]


def require_api_key(request: Request, session: SessionDep) -> Principal:
    """Dependency for the public REST API."""
    header = request.headers.get("X-API-Key") or request.headers.get("Authorization") or ""
    plaintext = header.removeprefix("Bearer ").strip()
    if not plaintext:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Send it in the X-API-Key header.",
        )

    record = services.resolve_api_key(session, plaintext)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key."
        )

    record.last_used_at = utcnow()
    session.commit()
    return Principal(user=None, account=record.account, api_key=record)


ApiPrincipalDep = Annotated[Principal, Depends(require_api_key)]


def login_redirect(next_url: str = "/app") -> RedirectResponse:
    target = "/login" if next_url in {"", "/app"} else f"/login?next={next_url}"
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
