"""Idempotent schema bootstrap.

`Base.metadata.create_all` creates new tables on both SQLite and Postgres, but it
never adds columns to tables that already exist. Production already has tender
rows, so this module adds the new nullable columns/indexes explicitly before the
app serves traffic. It works on an Engine or an Alembic connection and is safe
to run on every boot: it never drops data.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from app.database import Base

log = logging.getLogger(__name__)


def _timestamp_type(bind) -> str:
    dialect = getattr(getattr(bind, "dialect", None), "name", None) or getattr(
        getattr(getattr(bind, "engine", None), "dialect", None), "name", "sqlite"
    )
    return "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME"


def _extra_columns(bind) -> dict[str, dict[str, str]]:
    ts = _timestamp_type(bind)
    return {
        "tenders": {
            "municipality": "VARCHAR(120)",
            "notice_type": "VARCHAR(40)",
            "bid_opening_date": ts,
            "bid_security_npr": "DOUBLE PRECISION",
            "bid_validity_days": "INTEGER",
            "eligibility": "TEXT",
            "contact_info": "TEXT",
            "source_id": "INTEGER",
            "raw_source_id": "VARCHAR(200)",
            "canonical_tender_id": "INTEGER",
            "content_hash": "VARCHAR(64)",
            "procurement_type": "VARCHAR(40)",
            "ministry": "VARCHAR(300)",
            "department": "VARCHAR(300)",
            "first_seen_at": ts,
            "last_seen_at": ts,
            "seen_count": "INTEGER DEFAULT 1",
        },
        "tender_documents": {
            "file_format": "VARCHAR(20)",
            "file_size_bytes": "INTEGER",
            "published_date": ts,
            "download_status": "VARCHAR(30) DEFAULT 'unverified'",
            "last_checked_at": ts,
            "content_type": "VARCHAR(120)",
            "is_public": "BOOLEAN DEFAULT TRUE",
            "discovered_at": ts,
            "content_hash": "VARCHAR(64)",
            "http_status": "INTEGER",
            "is_available": "BOOLEAN",
            "storage_key": "VARCHAR(500)",
            "checked_count": "INTEGER DEFAULT 0",
        },
        "collector_sources": {
            "source_type": "VARCHAR(60)",
            "priority": "INTEGER DEFAULT 3",
            "last_run_id": "INTEGER",
        },
    }


_EXTRA_INDEXES = (
    ("ix_tenders_municipality", "tenders", "municipality"),
    ("ix_tenders_published_date", "tenders", "published_date"),
    ("ix_tenders_category_deadline", "tenders", "category, deadline"),
    ("ix_tenders_source_id", "tenders", "source_id"),
    ("ix_tenders_status_deadline", "tenders", "status, deadline"),
    ("ix_tenders_source_name", "tenders", "source_name"),
    ("ix_tenders_procurement_type", "tenders", "procurement_type"),
    ("ix_tenders_ministry", "tenders", "ministry"),
    ("ix_tenders_department", "tenders", "department"),
    ("ix_tenders_organization", "tenders", "organization_name"),
    ("ix_tenders_notice_number", "tenders", "notice_number"),
    ("ix_tender_documents_download_status", "tender_documents", "download_status"),
    ("ix_tender_documents_tender_id", "tender_documents", "tender_id"),
    ("ix_tender_documents_content_hash", "tender_documents", "content_hash"),
)


def _apply(connection, bind) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    for table, columns in _extra_columns(bind).items():
        if table not in existing_tables:
            continue
        current = {column["name"] for column in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name in current:
                continue
            log.info("Adding missing column %s.%s", table, name)
            connection.execute(text(f'ALTER TABLE {table} ADD COLUMN "{name}" {ddl}'))

    for index_name, table, columns in _EXTRA_INDEXES:
        if table not in existing_tables:
            continue
        try:
            connection.execute(
                text(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON {table} ({columns})')
            )
        except Exception:  # index creation must never block startup
            log.warning("Could not create index %s", index_name, exc_info=True)


def ensure_schema(bind: Engine | Connection) -> None:
    Base.metadata.create_all(bind=bind)
    if isinstance(bind, Engine):
        with bind.begin() as connection:
            _apply(connection, bind)
    else:
        _apply(bind, bind)
