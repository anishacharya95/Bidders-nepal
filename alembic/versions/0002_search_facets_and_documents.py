"""Advanced search facets and document viewer metadata.

Additive migration: new nullable columns on `tenders` (procurement type, ministry,
department) and `tender_documents` (discovered_at, content_hash, http status,
availability, storage reference, check counter) plus the indexes the search
filters rely on. Existing rows are preserved; derived facets are backfilled from
data the sources already publish.

Revision ID: 0002_search_facets
Revises: 0001_platform_schema
Create Date: 2026-11-26
"""
from __future__ import annotations

from alembic import op
from sqlalchemy.orm import Session

from app.database_schema import ensure_schema
from app.services.classification import backfill_classifications

revision = "0002_search_facets"
down_revision = "0001_platform_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    ensure_schema(bind)
    backfill_classifications(Session(bind=bind))


def downgrade() -> None:
    # No destructive downgrade: the added columns are nullable and unused by older code.
    pass
