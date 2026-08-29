"""Application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.deps import LoginRequired, login_redirect, render
from app.log import configure_logging, logger
from app.routes import api_v1, auth, dashboard, marketing, webhooks
from app.routes.marketing import page_context

DESCRIPTION = """
Programmatic access to local business lead data.

Authenticate with the `X-API-Key` header using a key created in your dashboard.
Submit a search, poll it until `status` is `completed`, then read `results` or
download the CSV.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.debug)
    init_db()
    logger.info(
        "%s starting (engine=%s, billing=%s)",
        settings.brand_name,
        settings.engine_mode,
        "on" if settings.billing_enabled else "off",
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.brand_name} API",
        description=DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    app.include_router(marketing.router)
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(api_v1.router)
    app.include_router(webhooks.router)

    @app.exception_handler(LoginRequired)
    async def _login_required(_: Request, exc: LoginRequired):
        return login_redirect(exc.next_url)

    @app.exception_handler(404)
    async def _not_found(request: Request, _):
        if request.url.path.startswith(("/api/", "/webhooks/")):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return render(
            "error.html",
            page_context(
                request, settings, None, code=404, message="That page does not exist."
            ),
            status_code=404,
        )

    return app


app = create_app()
