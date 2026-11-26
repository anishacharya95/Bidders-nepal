"""Single-process scheduler for the Render web service."""
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.collector import collect_public_notices

log = logging.getLogger(__name__)
_scheduler = None


def _run_collection():
    db = SessionLocal()
    try:
        result = collect_public_notices(db)
        log.info("Tender collection completed: %s", result)
    except Exception:
        log.exception("Scheduled tender collection failed")
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    if os.getenv("ENABLE_TENDER_COLLECTOR", "true").lower() not in {"1", "true", "yes"}:
        log.info("Tender collector scheduler disabled")
        return
    if _scheduler and _scheduler.running:
        return
    interval = max(60, int(os.getenv("TENDER_COLLECT_INTERVAL_MINUTES", "360")))
    _scheduler = BackgroundScheduler(timezone="Asia/Kathmandu", daemon=True)
    _scheduler.add_job(_run_collection, "interval", minutes=interval,
                       id="official-public-tender-discovery", max_instances=1,
                       coalesce=True, replace_existing=True)
    _scheduler.start()
    log.info("Tender collector scheduler started; interval=%s minutes", interval)


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
