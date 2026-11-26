"""Backwards-compatible scheduler module (delegates to app.scheduler)."""
from app.scheduler import scheduler_snapshot, start_scheduler, stop_scheduler

__all__ = ["start_scheduler", "stop_scheduler", "scheduler_snapshot"]
