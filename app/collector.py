"""Compatibility layer for the original collector module.

The implementation now lives in `app.collectors.*`; these names are kept so
existing deployments, scripts and tests keep working.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.collectors.extraction import (
    allowed_host as _allowed_host,
    allowed_host as _allowed,
    canonical_url as _canonical_url,
    category_from_text as _category,
    is_notice_detail_url as _is_notice_detail_url,
    looks_like_notice as _looks_like_notice,
    notice_number as _notice_number,
    organization_from_title as _organization_from_title,
    parse_deadline as _deadline,
)
from app.collectors.runner import run_collection


def collect_public_notices(db: Session, mode: str = "full", trigger: str = "legacy-api") -> dict:
    """Legacy entry point used by the original scheduler and admin endpoint."""
    return run_collection(db, mode=mode, trigger=trigger)


__all__ = [
    "_allowed",
    "_allowed_host",
    "_canonical_url",
    "_category",
    "_deadline",
    "_is_notice_detail_url",
    "_looks_like_notice",
    "_notice_number",
    "_organization_from_title",
    "collect_public_notices",
    "run_collection",
]
