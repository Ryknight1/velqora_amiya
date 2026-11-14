"""VelQora FastAPI application factory."""
from __future__ import annotations

import logging
import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .api.routes import auth, briefing, health, presentation, research
from .config import Settings, get_settings
from .dependencies import Container, build_container
from .exceptions import VelQoraError

logger = logging.getLogger("velqora")

_SECRET_PATTERNS = [
    (re.compile(r"tvly-[A-Za-z0-9_\-]{8,}"), "tvly-***"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-~+/=]{8,}"), "Bearer ***"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{8,}"), "gsk_***"),
    (re.compile(r"\bAIza[A-Za-z0-9_\-]{12,}"), "AIza***"),
]


class SecretRedactingFilter(logging.Filter):
    """Last line of defence: scrub anything that looks like an API key from log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern, replacement in _SECRET_PATTERNS:
            message = pattern.sub(replacement, message)
        record.msg, record.args = message, ()
        return True


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level, logging.INFO),
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    for handler in logging.getLogger().handlers:
        handler.addFilter(SecretRedactingFilter())
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _error(status: int, code: str, message: str, details=None, headers=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body, headers=headers)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        container.startup()
        logger.info("VelQora %s started (tavily=%s, bifrost=%s)", __version__,
                    "configured" if settings.tavily_configured else "NOT configured",
                    "configured" if settings.bifrost_configured else "NOT configured")
        yield
        await container.shutdown()

    app = FastAPI(title="VelQora API", version=__version__, lifespan=lifespan,
                  docs_url=None if settings.is_production else "/api/docs",
                  redoc_url=None, openapi_url=None if settings.is_production else "/api/openapi.json")

    app.state.container = container
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"], allow_headers=["Content-Type", "Authorization"],
                       max_age=600)

    # ---------------------------------------------------------------- errors
    @app.exception_handler(VelQoraError)
    async def _velqora(_: Request, exc: VelQoraError):
        if exc.status_code >= 500 and exc.status_code != 503:
            logger.warning("%s: %s", exc.code, exc.message)
        headers = {"Retry-After": str(exc.details["retry_after"])} if isinstance(exc.details, dict) and \
            "retry_after" in exc.details else None
        return _error(exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        problems = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
            msg = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
            problems.append({"field": ".".join(loc) or None, "message": msg})
        first = problems[0] if problems else {"message": "Invalid request."}
        return _error(422, "validation_error", first["message"], problems)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        message = "Not found." if exc.status_code == 404 else (exc.detail if isinstance(exc.detail, str) else "Request failed.")
        return _error(exc.status_code, "http_error", message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "internal_error", "Something went wrong on our side. Please try again.")

    # ---------------------------------------------------------------- middleware
    @app.middleware("http")
    async def _security_and_logging(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if not request.url.path.startswith("/api"):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
                "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        else:
            response.headers.setdefault("Cache-Control", "no-store")
        logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code,
                    (time.perf_counter() - started) * 1000)
        return response

    # ---------------------------------------------------------------- routes
    for module in (health, research, briefing, auth, presentation):
        app.include_router(module.router, prefix="/api")

    @app.get("/api", include_in_schema=False)
    async def _api_root():
        return {"service": "velqora-backend", "version": __version__, "docs": None if settings.is_production else "/api/docs"}

    # Serve the static frontend from the same origin (no CORS needed): http://localhost:8000/
    frontend = settings.frontend_dir
    if (frontend / "pages").is_dir() and (frontend / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")
        app.mount("/pages", StaticFiles(directory=frontend / "pages", html=True), name="pages")

        @app.get("/", include_in_schema=False)
        async def _index():
            return RedirectResponse("/pages/index.html")
    else:
        logger.info("Frontend directory not found at %s; serving API only.", frontend)
    return app


app = create_app()
