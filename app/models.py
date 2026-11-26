"""SQLAlchemy models for the tender platform.

Existing tables (users, tenders, tender_documents, collector_sources, audit_logs)
keep their columns; new platform tables are additive. Nullable columns are used
for data sources frequently do not publish.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (
        Index("ix_tenders_deadline_status", "deadline", "status"),
        Index("ix_tenders_category_deadline", "category", "deadline"),
        Index("ix_tenders_status_deadline", "status", "deadline"),
        Index("ix_tenders_source_name", "source_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    notice_number: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    organization_name: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str] = mapped_column(String(40), default="Other", index=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    municipality: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    bid_opening_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_budget_npr: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_security_npr: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eligibility: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    notice_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Facets derived from the published category and procuring-entity name. They
    # are never invented: a value is stored only when the source text supports it.
    procurement_type: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    ministry: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    department: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    source_name: Mapped[str] = mapped_column(String(200), default="Manual submission")
    source_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    raw_source_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    canonical_tender_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)
    seen_count: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    documents: Mapped[list["TenderDocument"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    changes: Mapped[list["TenderChange"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )


class TenderDocument(Base):
    __tablename__ = "tender_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(500), default="Bid document")
    url: Mapped[str] = mapped_column(String(1500))
    document_type: Mapped[str] = mapped_column(String(40), default="Other")
    source_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    file_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    download_status: Mapped[str] = mapped_column(String(30), default="unverified")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Optional local mirror reference; the original URL is always preserved.
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    checked_count: Mapped[int] = mapped_column(Integer, default=0)

    tender: Mapped["Tender"] = relationship(back_populates="documents")


class Source(Base):
    """Registered procurement source (agency, utility or one of the 753 local units)."""

    __tablename__ = "source_registry"
    __table_args__ = (UniqueConstraint("slug", name="uq_source_registry_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    name_ne: Mapped[str | None] = mapped_column(String(300), nullable=True)
    organization_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_type: Mapped[str] = mapped_column(String(60), default="agency", index=True)
    level: Mapped[str] = mapped_column(String(30), default="central", index=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    municipality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    official_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tender_page_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    collector_key: Mapped[str] = mapped_column(String(60), default="generic_html", index=True)
    discovery_status: Mapped[str] = mapped_column(String(40), default="unregistered", index=True)
    requires_authorization: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    notices_found: Mapped[int] = mapped_column(Integer, default=0)
    documents_found: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    trigger: Mapped[str] = mapped_column(String(40), default="manual")
    mode: Mapped[str] = mapped_column(String(30), default="priority")
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sources_checked: Mapped[int] = mapped_column(Integer, default=0)
    sources_ok: Mapped[int] = mapped_column(Integer, default=0)
    sources_failed: Mapped[int] = mapped_column(Integer, default=0)
    candidates_found: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    documents_found: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    scans: Mapped[list["SourceScan"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class SourceScan(Base):
    __tablename__ = "source_scans"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("collection_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_name: Mapped[str] = mapped_column(String(300), default="Unknown source")
    url: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), default="ok")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    documents_found: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    run: Mapped["CollectionRun | None"] = relationship(back_populates="scans")


class TenderChange(Base):
    __tablename__ = "tender_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"), index=True
    )
    change_type: Mapped[str] = mapped_column(String(40), index=True)
    field: Mapped[str | None] = mapped_column(String(60), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    tender: Mapped["Tender"] = relationship(back_populates="changes")


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(200))
    filters_json: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CollectorSource(Base):
    """Legacy per-page health records exposed by the original admin endpoint."""

    __tablename__ = "collector_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1500), unique=True, index=True)
    source_name: Mapped[str] = mapped_column(String(200), default="Government source")
    source_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    last_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="never_checked", index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    notices_found: Mapped[int] = mapped_column(Integer, default=0)
    documents_found: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
