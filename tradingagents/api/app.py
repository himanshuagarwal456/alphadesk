"""FastAPI ASGI app and CLI entrypoint.

Uvicorn target (factory mode)::

    uvicorn tradingagents.api.app:create_app --factory

CLI entry: ``alphadesk-api``
"""

from __future__ import annotations

import os

from tradingagents.persistence.session import SessionFactory, create_engine_from_url
from tradingagents.persistence.settings import load_persistence_settings


def create_app(
    *,
    database_url: str | None = None,
    create_schema: bool = True,
):
    """Build the FastAPI app. Imported lazily so core installs stay lean."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse, RedirectResponse
        from fastapi.staticfiles import StaticFiles
        from sqlalchemy import text
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            'AlphaDesk API requires the server extra: pip install "alphadesk[server]"'
        ) from exc

    from tradingagents.observability.logging import bind_trace_id, get_trace_id
    from tradingagents.web import STATIC_DIR

    from .deps import AppState
    from .v1.router import api_router

    settings = load_persistence_settings()
    url = database_url or settings.database_url
    factory = SessionFactory(create_engine_from_url(url))
    if create_schema:
        factory.create_all()

    application = FastAPI(
        title=settings.api_title,
        version="0.12.0",
        description="AlphaDesk research and intelligence API (v1).",
    )
    application.state.alphadesk = AppState(
        session_factory=factory,
        settings=settings,
    )
    application.include_router(api_router, prefix="/v1")

    @application.middleware("http")
    async def _trace_and_cache(request: Request, call_next):
        incoming = request.headers.get("X-Trace-Id")
        trace_id = bind_trace_id(incoming)
        response = await call_next(request)
        response.headers["X-Trace-Id"] = get_trace_id() or trace_id
        path = request.url.path
        if path == "/app" or path.startswith("/app"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "alphadesk"}

    @application.get("/health/ready")
    def health_ready():
        try:
            with factory.session_scope() as session:
                session.execute(text("SELECT 1"))
            return {"status": "ready", "database": "ok"}
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "database": str(exc)},
            )

    @application.get("/")
    def root_redirect():
        return RedirectResponse(url="/app/")

    if STATIC_DIR.is_dir():
        application.mount(
            "/app",
            StaticFiles(directory=str(STATIC_DIR), html=True),
            name="alphadesk-web",
        )

    return application


def main() -> None:
    """CLI entry: ``alphadesk-api``."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            'Install the server extra first: pip install "alphadesk[server]"'
        ) from exc

    host = os.environ.get("ALPHADESK_API_HOST", "127.0.0.1")
    port = int(os.environ.get("ALPHADESK_API_PORT", "8000"))
    uvicorn.run(
        "tradingagents.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=False,
    )
