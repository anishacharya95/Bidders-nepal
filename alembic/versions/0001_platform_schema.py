"""Initial platform schema.

Production already contains the original `tenders` table. This migration is
therefore additive and idempotent: it creates missing tables (source registry,
collection runs, scans, changes, saved searches) and adds nullable columns that
were introduced with the platform. It never drops or rewrites existing rows.

Revision ID: 0001_platform_schema
Revises:
Create Date: 2026-11-26
"""
from __future__ import annotations

from alembic import op

from app import models  # noqa: F401  (registers metadata)
from app.database_schema import ensure_schema

revision = "0001_platform_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    ensure_schema(op.get_bind())


def downgrade() -> None:
    # Deliberately no destructive downgrade: this migration protects production data.
    pass
