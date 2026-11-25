from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from backend.app.models.enquiry import EnquiryStatus, EnquiryCategory, EnquiryPriority
from backend.app.schemas.draft import ResponseDraftResponse
from backend.app.schemas.audit import AuditLogResponse


class EnquiryBase(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=255)
    customer_email: EmailStr
    channel: str = Field(default="email", max_length=50)
    subject: str = Field(..., min_length=3, max_length=255)
    message: str = Field(..., min_length=5)
    order_number: Optional[str] = Field(None, max_length=100)


class EnquiryCreate(EnquiryBase):
    pass


class EnquiryUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    category: Optional[EnquiryCategory] = None
    status: Optional[EnquiryStatus] = None
    priority: Optional[EnquiryPriority] = None
    sentiment: Optional[str] = None
    ai_summary: Optional[str] = None
    order_number: Optional[str] = None


class EnquiryResponse(EnquiryBase):
    id: int
    category: EnquiryCategory
    status: EnquiryStatus
    priority: EnquiryPriority
    sentiment: str
    ai_summary: Optional[str] = None
    ai_confidence: float = 0.0
    created_at: datetime
    updated_at: datetime
    drafts_count: int = 0
    latest_draft_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class EnquiryDetailResponse(EnquiryResponse):
    drafts: List[ResponseDraftResponse] = []
    audit_logs: List[AuditLogResponse] = []

    model_config = ConfigDict(from_attributes=True)
