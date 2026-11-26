"""Bidders Nepal API — application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.api import admin, admin_ui, auth, public
from app.collectors.registry import sync_registry
from app.config import settings
from app.database import SessionLocal, engine, get_db
from app.database_schema import ensure_schema
from app.models import Source, Tender, TenderDocument, User
from app.scheduler import scheduler_snapshot, start_scheduler, stop_scheduler
from app.security import hash_password

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("bidders_nepal")


def seed_admin() -> None:
    if not (settings.admin_email and settings.admin_password):
        log.warning("ADMIN_EMAIL/ADMIN_PASSWORD not configured: admin API and dashboard cannot be used")
        return
    with SessionLocal() as db:
        user = db.query(User).filter(func.lower(User.email) == settings.admin_email.lower()).first()
        if not user:
            db.add(
                User(
                    email=settings.admin_email.lower(),
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                )
            )
            db.commit()
            log.info("Seeded admin account %s", settings.admin_email.lower())
        elif not user.is_active or user.role != "admin":
            user.is_active = True
            user.role = "admin"
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema(engine)
    seed_admin()
    try:
        with SessionLocal() as db:
            result = sync_registry(db)
            log.info("Source registry synced: %s", result)
    except Exception:
        log.exception("Source registry sync failed at startup")
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Automated Nepal public tender discovery: sources, collection runs, documents, "
        "duplicate detection and a review workflow. Public endpoints never expose admin operations."
    ),
    lifespan=lifespan,
)

origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static", check_dir=False), name="static")

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(admin_ui.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Send unauthenticated dashboard visitors to the login page."""
    location = exc.headers.get("Location") if exc.headers else None
    if location and location.startswith("/admin"):
        return RedirectResponse(location, status_code=303)
    if exc.status_code == 401 and request.url.path.startswith("/admin"):
        return RedirectResponse("/admin/login", status_code=303)
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
        headers={k: v for k, v in (exc.headers or {}).items() if k.lower() != "location"} or None,
    )


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "health": "/health",
        "tenders": "/api/v1/tenders/all",
        "coverage": "/api/v1/coverage",
        "admin_dashboard": "/admin",
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    database_ok = True
    database_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - depends on live DB
        database_ok = False
        database_error = str(exc)[:200]
    return {
        "status": "ok" if database_ok else "degraded",
        "service": "bidders-nepal-api",
        "version": settings.version,
        "time": datetime.now(timezone.utc).isoformat(),
        "database": {"ok": database_ok, "dialect": db.bind.dialect.name, "error": database_error},
        "collector": {
            "enabled": settings.collector_enabled,
            "priority_interval_minutes": settings.priority_interval_minutes,
            "scheduler": scheduler_snapshot().get("running", False),
        },
    }


@app.get("/health/data")
def health_data(db: Session = Depends(get_db)):
    """Non-secret counts used to verify collection is writing real records."""
    return {
        "sources": db.query(Source).count(),
        "sources_scanned": db.query(Source).filter(Source.last_success_at.isnot(None)).count(),
        "tenders": db.query(Tender).count(),
        "pending": db.query(Tender).filter(Tender.verification_status == "pending").count(),
        "documents": db.query(TenderDocument).count(),
        "latest_tender_id": db.query(func.max(Tender.id)).scalar(),
        "time": datetime.now(timezone.utc).isoformat(),
    }
