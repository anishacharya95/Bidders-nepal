"""Central configuration. Every value is environment driven so Render can tune it."""
from __future__ import annotations

import os


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Settings:
    app_name = os.getenv("APP_NAME", "Bidders Nepal API")
    version = "2.0.0"

    # Database / security
    database_url = os.getenv("DATABASE_URL", "sqlite:///./bidders_nepal.db")
    jwt_secret = os.getenv("JWT_SECRET", "")
    jwt_exp_minutes = _int("JWT_EXP_MINUTES", 720, 5)
    admin_email = os.getenv("ADMIN_EMAIL", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    cors_origins = os.getenv("CORS_ORIGINS", "*")

    # Admin dashboard (cookie session)
    admin_cookie_name = os.getenv("ADMIN_COOKIE_NAME", "bn_admin")
    admin_session_minutes = _int("ADMIN_SESSION_MINUTES", 720, 5)
    admin_cookie_secure = _bool("ADMIN_COOKIE_SECURE", True)

    # Collector scheduling
    collector_enabled = _bool("ENABLE_TENDER_COLLECTOR", True)
    # Legacy variable kept for Render compatibility: it used to be the single interval.
    priority_interval_minutes = _int(
        "TENDER_PRIORITY_INTERVAL_MINUTES",
        _int("TENDER_COLLECT_INTERVAL_MINUTES", 20, 10),
        10,
    )
    full_scan_cron = os.getenv("TENDER_FULL_SCAN_CRON", "0 2 * * *")
    full_scan_enabled = _bool("TENDER_FULL_SCAN_ENABLED", True)
    startup_scan_enabled = _bool("TENDER_STARTUP_SCAN", True)
    startup_scan_delay_seconds = _int("TENDER_STARTUP_SCAN_DELAY_SECONDS", 25, 5)
    collector_timezone = os.getenv("TENDER_TIMEZONE", "Asia/Kathmandu")

    # Collector limits (protect free hosting and source websites)
    collector_priority_limit = _int("TENDER_PRIORITY_SOURCE_LIMIT", 24, 1)
    collector_full_limit = _int("TENDER_FULL_SOURCE_LIMIT", 120, 1)
    collector_run_budget_seconds = _int("TENDER_RUN_BUDGET_SECONDS", 240, 30)
    collector_max_pages_per_source = _int("TENDER_MAX_PAGES_PER_SOURCE", 3, 1)
    collector_detail_fetch_limit = _int("TENDER_DETAIL_FETCH_LIMIT", 20, 0)
    collector_http_timeout = _int("TENDER_HTTP_TIMEOUT_SECONDS", 18, 5)
    collector_host_delay_seconds = _float("TENDER_HOST_DELAY_SECONDS", 1.5)
    collector_max_response_bytes = _int("TENDER_MAX_RESPONSE_BYTES", 3_000_000, 100_000)
    collector_probe_documents = _bool("TENDER_PROBE_DOCUMENTS", True)

    # Local government website discovery (incremental, respectful)
    local_discovery_enabled = _bool("TENDER_LOCAL_DISCOVERY", True)
    local_discovery_batch = _int("TENDER_LOCAL_DISCOVERY_BATCH", 8, 1)

    extra_source_urls = os.getenv("TENDER_SOURCE_URLS", "")
    # JSON notice feeds, e.g. https://bidders-nepal-api.onrender.com/api/v1/tenders/all
    # Each entry is registered as a `json_api` source and fetched even when it
    # is not a .gov.np host, because an operator configured it explicitly.
    json_source_urls = os.getenv("TENDER_JSON_SOURCE_URLS", "")
    json_source_hosts = os.getenv("TENDER_JSON_SOURCE_HOSTS", "")
    user_agent = os.getenv(
        "TENDER_USER_AGENT",
        "BiddersNepalBot/2.0 (+https://bidders-nepal-api.onrender.com; public notice discovery; contact: admin@biddersnepal.app)",
    )


settings = Settings()
