"""Signup, login and logout."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app import services
from app.deps import OptionalUserDep, SessionDep, SettingsDep, render
from app.models import utcnow
from app.plans import DEFAULT_PLAN, PLANS
from app.routes.marketing import page_context
from app.security import password_problem, sign_session, verify_password

router = APIRouter()

# Only redirect to paths inside this app, never to an attacker-supplied host.
SAFE_PREFIXES = ("/app",)


def safe_next(candidate: str) -> str:
    if candidate.startswith(SAFE_PREFIXES) and not candidate.startswith("//"):
        return candidate
    return "/app"


def _auth_page(request, settings, mode: str, **extra):
    if mode == "signup":
        base = {
            "mode": "signup",
            "heading": "Start free",
            "subheading": "100 leads on us. No card needed.",
            "action": "/signup",
            "submit_label": "Create my account",
            "alt_text": "Already have an account?",
            "alt_href": "/login",
            "alt_label": "Sign in",
        }
    else:
        base = {
            "mode": "login",
            "heading": "Welcome back",
            "subheading": "Sign in to run your next search.",
            "action": "/login",
            "submit_label": "Sign in",
            "alt_text": "New here?",
            "alt_href": "/signup",
            "alt_label": "Start free",
        }
    base.setdefault("email", "")
    base.setdefault("company_name", "")
    base.setdefault("next_url", "/app")
    base.setdefault("plan_code", "")
    base.update(extra)
    return render(
        "auth.html", page_context(request, settings, None, **base)
    )


def _set_session_cookie(response, settings, user_id: str) -> None:
    response.set_cookie(
        settings.session_cookie,
        sign_session(user_id),
        max_age=settings.session_max_age,
        httponly=True,
        samesite="lax",
        secure=settings.public_url.startswith("https://"),
        path="/",
    )


@router.get("/signup", response_class=HTMLResponse)
def signup_page(
    request: Request,
    settings: SettingsDep,
    user: OptionalUserDep,
    plan: str = "",
    keyword: str = "",
):
    if user is not None:
        return RedirectResponse("/app", status_code=status.HTTP_303_SEE_OTHER)
    if not settings.signup_enabled:
        return _auth_page(
            request, settings, "signup", error="Signups are currently closed."
        )
    next_url = f"/app?keyword={keyword}" if keyword else "/app"
    return _auth_page(
        request,
        settings,
        "signup",
        plan_code=plan if plan in PLANS else "",
        next_url=next_url,
    )


@router.post("/signup")
def signup_submit(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    company_name: Annotated[str, Form()] = "",
    plan: Annotated[str, Form()] = "",
    next: Annotated[str, Form()] = "/app",
):
    if not settings.signup_enabled:
        return _auth_page(
            request, settings, "signup", error="Signups are currently closed."
        )

    problem = password_problem(password)
    if problem:
        return _auth_page(
            request, settings, "signup", error=problem, email=email,
            company_name=company_name, plan_code=plan, next_url=next,
        )

    try:
        user = services.create_account_with_owner(
            session,
            email=email,
            password=password,
            company_name=company_name,
            plan_code=DEFAULT_PLAN,
        )
    except services.SignupError as exc:
        return _auth_page(
            request, settings, "signup", error=str(exc), email=email,
            company_name=company_name, plan_code=plan, next_url=next,
        )

    session.commit()

    # A plan chosen on the pricing page carries through to checkout after signup.
    target = f"/app/billing?plan={plan}" if plan in PLANS and plan != DEFAULT_PLAN else safe_next(next)
    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(response, settings, user.id)
    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request, settings: SettingsDep, user: OptionalUserDep, next: str = "/app"
):
    if user is not None:
        return RedirectResponse("/app", status_code=status.HTTP_303_SEE_OTHER)
    return _auth_page(request, settings, "login", next_url=safe_next(next))


@router.post("/login")
def login_submit(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/app",
):
    user = services.find_user_by_email(session, email)
    if user is None or not verify_password(user.password_hash, password):
        # Deliberately identical message for unknown email and wrong password.
        return _auth_page(
            request,
            settings,
            "login",
            error="That email and password do not match.",
            email=email,
            next_url=safe_next(next),
        )

    user.last_login_at = utcnow()
    session.commit()

    response = RedirectResponse(safe_next(next), status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(response, settings, user.id)
    return response


@router.post("/logout")
def logout(settings: SettingsDep):
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.session_cookie, path="/")
    return response
