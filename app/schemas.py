from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Category = Literal["Works", "Goods", "Consultancy", "Services", "Other"]


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class TenderCreate(BaseModel):
    title: str = Field(min_length=5, max_length=500)
    notice_number: str | None = None
    organization_name: str = Field(min_length=2, max_length=300)
    category: Category = "Other"
    province: str | None = None
    district: str | None = None
    municipality: str | None = None
    description: str | None = None
    published_date: datetime | None = None
    deadline: datetime | None = None
    bid_opening_date: datetime | None = None
    estimated_budget_npr: float | None = Field(default=None, ge=0)
    bid_security_npr: float | None = Field(default=None, ge=0)
    bid_validity_days: int | None = Field(default=None, ge=0, le=3650)
    eligibility: str | None = None
    contact_info: str | None = None
    notice_type: str | None = None
    source_name: str = "Manual submission"
    source_url: str | None = None
    document_url: str | None = None


class TenderUpdate(BaseModel):
    title: str | None = None
    notice_number: str | None = None
    organization_name: str | None = None
    category: Category | None = None
    province: str | None = None
    district: str | None = None
    municipality: str | None = None
    description: str | None = None
    published_date: datetime | None = None
    deadline: datetime | None = None
    bid_opening_date: datetime | None = None
    estimated_budget_npr: float | None = Field(default=None, ge=0)
    bid_security_npr: float | None = Field(default=None, ge=0)
    bid_validity_days: int | None = Field(default=None, ge=0, le=3650)
    eligibility: str | None = None
    contact_info: str | None = None
    notice_type: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    document_url: str | None = None
    status: Literal["open", "closed", "cancelled", "awarded"] | None = None
    verification_status: Literal["pending", "verified", "rejected"] | None = None


class TenderDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    url: str
    document_type: str
    source_url: str | None = None
    file_format: str | None = None
    file_size_bytes: int | None = None
    published_date: datetime | None = None
    download_status: str | None = None
    last_checked_at: datetime | None = None
    content_type: str | None = None
    is_public: bool | None = True


class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    notice_number: str | None
    organization_name: str
    category: str
    province: str | None
    district: str | None
    municipality: str | None = None
    description: str | None
    published_date: datetime | None
    deadline: datetime | None
    bid_opening_date: datetime | None = None
    estimated_budget_npr: float | None
    bid_security_npr: float | None = None
    bid_validity_days: int | None = None
    eligibility: str | None = None
    contact_info: str | None = None
    notice_type: str | None = None
    source_name: str
    source_url: str | None
    document_url: str | None
    documents: list[TenderDocumentOut] = Field(default_factory=list)
    status: str
    verification_status: str
    created_at: datetime
    updated_at: datetime
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    seen_count: int | None = None


class TenderChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    change_type: str
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    note: str | None = None
    source_url: str | None = None
    detected_at: datetime


class SavedSearchCreate(BaseModel):
    device_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    label: str = Field(min_length=2, max_length=200)
    filters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("filters")
    @classmethod
    def limit_filters(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 20:
            raise ValueError("Too many filters")
        allowed = {
            "q",
            "category",
            "province",
            "district",
            "municipality",
            "organization",
            "status",
            "verification_status",
            "has_documents",
        }
        return {key: item for key, item in value.items() if key in allowed and item not in (None, "")}


class SavedSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: str
    label: str
    filters_json: str
    active: bool
    created_at: datetime


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    name_ne: str | None = None
    organization_name: str | None = None
    source_type: str
    level: str
    province: str | None = None
    district: str | None = None
    municipality: str | None = None
    official_website: str | None = None
    tender_page_url: str | None = None
    collector_key: str
    discovery_status: str
    requires_authorization: bool
    active: bool
    priority: int
    notes: str | None = None
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int
    notices_found: int
    documents_found: int


class SourceCreate(BaseModel):
    name: str = Field(min_length=3, max_length=300)
    name_ne: str | None = Field(default=None, max_length=300)
    organization_name: str | None = Field(default=None, max_length=300)
    source_type: str = Field(default="agency", max_length=60)
    level: str = Field(default="central", max_length=30)
    province: str | None = None
    district: str | None = None
    municipality: str | None = None
    official_website: str | None = Field(default=None, max_length=500)
    tender_page_url: str | None = Field(default=None, max_length=1000)
    collector_key: Literal["generic_html", "ppmo", "nea", "directory_mofaga", "manual"] = "generic_html"
    active: bool = True
    priority: int = Field(default=3, ge=1, le=5)
    requires_authorization: bool = False
    notes: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    organization_name: str | None = Field(default=None, max_length=300)
    official_website: str | None = Field(default=None, max_length=500)
    tender_page_url: str | None = Field(default=None, max_length=1000)
    collector_key: Literal["generic_html", "ppmo", "nea", "directory_mofaga", "manual"] | None = None
    discovery_status: str | None = Field(default=None, max_length=40)
    active: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    requires_authorization: bool | None = None
    notes: str | None = None
