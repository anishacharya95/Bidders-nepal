from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Float, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def utcnow():
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
    __table_args__ = (Index("ix_tenders_deadline_status", "deadline", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    notice_number: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    organization_name: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str] = mapped_column(String(40), default="Other", index=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    estimated_budget_npr: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_name: Mapped[str] = mapped_column(String(200), default="Manual submission")
    source_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    documents: Mapped[list["TenderDocument"]] = relationship(back_populates="tender", cascade="all, delete-orphan")

class TenderDocument(Base):
    __tablename__ = "tender_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(500), default="Bid document")
    url: Mapped[str] = mapped_column(String(1500))
    document_type: Mapped[str] = mapped_column(String(40), default="Other")
    source_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    tender: Mapped["Tender"] = relationship(back_populates="documents")

class CollectorSource(Base):
    __tablename__ = "collector_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1500), unique=True, index=True)
    source_name: Mapped[str] = mapped_column(String(200), default="Government source")
    status: Mapped[str] = mapped_column(String(30), default="never_checked", index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    notices_found: Mapped[int] = mapped_column(default=0)
    documents_found: Mapped[int] = mapped_column(default=0)
    consecutive_failures: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
