"""Background scheduling for collection, full scans and local-site discovery."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.collectors.discovery import discover_local_governments
from app.collectors.registry import sync_registry
from app.collectors.runner import run_collection
from app.config import settings
from app.database import SessionLocal
from app.services.document_refresh import refresh_documents

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_last_runs: dict[str, str] = {}


def _run(mode: str, trigger: str) -> dict | None:
    db = SessionLocal()
    try:
        sync_registry(db)
        result = run_collection(db, mode=mode, trigger=trigger)
        _last_runs[mode] = datetime.now(timezone.utc).isoformat()
        log.info(
            "Scheduled %s collection finished: status=%s inserted=%s failed=%s",
            mode,
            result.get("status"),
            result.get("inserted"),
            result.get("sources_failed"),
        )
        return result
    except Exception:
        log.exception("Scheduled %s collection failed", mode)
        db.rollback()
        return None
    finally:
        db.close()


def _discover() -> None:
    db = SessionLocal()
    try:
        result = discover_local_governments(db)
        log.info("Local-government website discovery: %s", result)
    except Exception:
        log.exception("Local-government website discovery failed")
        db.rollback()
    finally:
        db.close()


def _refresh_documents() -> None:
    """Re-check document reachability so broken links are labelled honestly."""
    db = SessionLocal()
    try:
        result = refresh_documents(db)
        log.info("Document availability refresh: %s", result)
    except Exception:
        log.exception("Document availability refresh failed")
        db.rollback()
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if not settings.collector_enabled:
        log.info("Tender collector scheduler disabled by configuration")
        return
    if _scheduler and _scheduler.running:
        return

    scheduler = BackgroundScheduler(timezone=settings.collector_timezone, daemon=True)
    from datetime import datetime as dt

    tz = scheduler.timezone
    scheduler.add_job(
        lambda: _run("priority", "schedule"),
        "interval",
        minutes=settings.priority_interval_minutes,
        next_run_time=dt.now(tz) + timedelta(seconds=settings.startup_scan_delay_seconds),
        id="priority-source-scan",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=900,
        replace_existing=True,
    )

    if settings.full_scan_enabled:
        try:
            scheduler.add_job(
                lambda: _run("full", "daily_schedule"),
                CronTrigger.from_crontab(settings.full_scan_cron, timezone=tz),
                id="daily-full-scan",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
                replace_existing=True,
            )
        except ValueError:
            log.warning("Invalid TENDER_FULL_SCAN_CRON=%r; daily scan disabled", settings.full_scan_cron)

    if settings.document_refresh_enabled:
        scheduler.add_job(
            _refresh_documents,
            "interval",
            hours=settings.document_refresh_hours,
            id="document-availability-refresh",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1800,
            replace_existing=True,
        )

    if settings.local_discovery_enabled:
        scheduler.add_job(
            _discover,
            CronTrigger(hour=3, minute=15, timezone=tz),
            id="local-website-discovery",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

    scheduler.start()
    _scheduler = scheduler
    log.info(
        "Collector scheduler started: priority every %s minutes, full scan cron %r, timezone %s",
        settings.priority_interval_minutes,
        settings.full_scan_cron,
        settings.collector_timezone,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def scheduler_snapshot() -> dict:
    if not _scheduler or not _scheduler.running:
        return {"running": False, "jobs": [], "last_runs": _last_runs}
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
        )
    return {
        "running": True,
        "timezone": str(_scheduler.timezone),
        "jobs": jobs,
        "last_runs": _last_runs,
        "settings": {
            "priority_interval_minutes": settings.priority_interval_minutes,
            "full_scan_cron": settings.full_scan_cron,
            "local_discovery_enabled": settings.local_discovery_enabled,
        },
    }
