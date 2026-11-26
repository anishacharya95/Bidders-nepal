from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Literal

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
    description: str | None = None
    published_date: datetime | None = None
    deadline: datetime | None = None
    estimated_budget_npr: float | None = Field(default=None, ge=0)
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
    description: str | None = None
    published_date: datetime | None = None
    deadline: datetime | None = None
    estimated_budget_npr: float | None = Field(default=None, ge=0)
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
    source_url: str | None

class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    notice_number: str | None
    organization_name: str
    category: str
    province: str | None
    district: str | None
    description: str | None
    published_date: datetime | None
    deadline: datetime | None
    estimated_budget_npr: float | None
    source_name: str
    source_url: str | None
    document_url: str | None
    documents: list[TenderDocumentOut] = Field(default_factory=list)
    status: str
    verification_status: str
    created_at: datetime
    updated_at: datetime
