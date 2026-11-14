"""Environment-based configuration.

All secrets come from environment variables (optionally loaded from backend/.env).
Nothing here is ever sent to the browser or written to logs.
"""
from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

logger = logging.getLogger("velqora.config")


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def _bool(name: str, default: bool) -> bool:
    raw = _env(name, "")
    if raw == "":
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(_env(name, str(default))))
    except ValueError:
        logger.warning("Invalid integer for %s; using default %s", name, default)
        return default


def _float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(_env(name, str(default))))
    except ValueError:
        logger.warning("Invalid number for %s; using default %s", name, default)
        return default


def _list(name: str, default: str) -> List[str]:
    return [item.strip() for item in _env(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # --- app ---
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: List[str] = field(
        default_factory=lambda: [
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    frontend_dir: Path = PROJECT_DIR / "frontend"
    exports_dir: Path = BACKEND_DIR / "exports"
    trust_proxy: bool = False

    # --- database (SQLite by default; replaceable layer) ---
    database_path: str = str(BACKEND_DIR / "velqora.db")

    # --- auth ---
    jwt_secret: str = ""
    jwt_expire_minutes: int = 60 * 24
    require_auth: bool = False

    # --- Tavily ---
    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"
    tavily_search_depth: str = "basic"          # basic = 1 credit, advanced = 2 credits
    tavily_timeout: float = 25.0
    tavily_max_retries: int = 2
    tavily_max_searches_per_research: int = 6
    tavily_daily_call_cap: int = 100
    tavily_cache_ttl: int = 6 * 3600
    tavily_min_score: float = 0.05

    # --- Bifrost (OpenAI-compatible LLM gateway) ---
    bifrost_base_url: str = ""
    bifrost_api_key: str = ""
    bifrost_model: str = ""
    bifrost_fallback_model: str = ""           # optional: tried when primary model returns 503/429
    bifrost_auth_mode: str = "bearer"          # bearer | virtual_key
    bifrost_timeout: float = 90.0
    bifrost_max_retries: int = 2
    bifrost_max_tokens: int = 2500
    bifrost_temperature: float = 0.1
    bifrost_json_mode: bool = False
    llm_json_retries: int = 2

    # --- research / briefing behaviour ---
    research_window_days: int = 30
    max_sources: int = 12
    llm_max_sources: int = 10
    llm_snippet_chars: int = 600
    verify_min_overlap: float = 0.6
    max_concurrent_jobs: int = 3

    # --- rate limits (per client IP) ---
    rate_limit_per_minute: int = 60
    research_rate_limit_per_hour: int = 12

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def tavily_configured(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def bifrost_configured(self) -> bool:
        return bool(self.bifrost_base_url and self.bifrost_model)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BACKEND_DIR / ".env", override=False)
        jwt_secret = _env("JWT_SECRET")
        if not jwt_secret:
            jwt_secret = secrets.token_urlsafe(48)
            logger.warning("JWT_SECRET is not set; generated a temporary one (sessions reset on restart).")
        depth = _env("TAVILY_SEARCH_DEPTH", "basic").lower()
        if depth not in {"basic", "advanced", "fast", "ultra-fast"}:
            depth = "basic"
        auth_mode = _env("BIFROST_AUTH_MODE", "bearer").lower()
        if auth_mode not in {"bearer", "virtual_key"}:
            auth_mode = "bearer"
        frontend = _env("FRONTEND_DIR")
        exports_path = _env("EXPORTS_DIR")
        return cls(
            app_env=_env("APP_ENV", "development"),
            log_level=_env("LOG_LEVEL", "INFO").upper(),
            cors_origins=_list(
                "CORS_ORIGINS",
                "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000,"
                "http://localhost:3000,http://127.0.0.1:3000",
            ),
            frontend_dir=Path(frontend) if frontend else PROJECT_DIR / "frontend",
            exports_dir=Path(exports_path) if exports_path else BACKEND_DIR / "exports",
            trust_proxy=_bool("TRUST_PROXY", False),
            database_path=_env("DATABASE_PATH", str(BACKEND_DIR / "velqora.db")),
            jwt_secret=jwt_secret,
            jwt_expire_minutes=_int("JWT_EXPIRE_MINUTES", 60 * 24, 5),
            require_auth=_bool("REQUIRE_AUTH", False),
            tavily_api_key=_env("TAVILY_API_KEY"),
            tavily_base_url=_env("TAVILY_BASE_URL", "https://api.tavily.com").rstrip("/"),
            tavily_search_depth=depth,
            tavily_timeout=_float("TAVILY_TIMEOUT", 25.0, 3.0),
            tavily_max_retries=_int("TAVILY_MAX_RETRIES", 2),
            tavily_max_searches_per_research=_int("TAVILY_MAX_SEARCHES_PER_RESEARCH", 6, 1),
            tavily_daily_call_cap=_int("TAVILY_DAILY_CALL_CAP", 100, 1),
            tavily_cache_ttl=_int("TAVILY_CACHE_TTL", 6 * 3600),
            tavily_min_score=_float("TAVILY_MIN_SCORE", 0.05),
            bifrost_base_url=_env("BIFROST_BASE_URL").rstrip("/"),
            bifrost_api_key=_env("BIFROST_API_KEY"),
            bifrost_model=_env("BIFROST_MODEL"),
            bifrost_fallback_model=_env("BIFROST_FALLBACK_MODEL"),
            bifrost_auth_mode=auth_mode,
            bifrost_timeout=_float("BIFROST_TIMEOUT", 90.0, 5.0),
            bifrost_max_retries=_int("BIFROST_MAX_RETRIES", 2),
            bifrost_max_tokens=_int("BIFROST_MAX_TOKENS", 1800, 200),
            bifrost_temperature=_float("BIFROST_TEMPERATURE", 0.1),
            bifrost_json_mode=_bool("BIFROST_JSON_MODE", False),
            llm_json_retries=_int("LLM_JSON_RETRIES", 1),
            research_window_days=_int("RESEARCH_WINDOW_DAYS", 30, 1),
            max_sources=_int("MAX_SOURCES", 12, 3),
            llm_max_sources=_int("LLM_MAX_SOURCES", 10, 3),
            llm_snippet_chars=_int("LLM_SNIPPET_CHARS", 600, 150),
            verify_min_overlap=_float("VERIFY_MIN_OVERLAP", 0.6),
            max_concurrent_jobs=_int("MAX_CONCURRENT_JOBS", 3, 1),
            rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", 60, 5),
            research_rate_limit_per_hour=_int("RESEARCH_RATE_LIMIT_PER_HOUR", 12, 1),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
