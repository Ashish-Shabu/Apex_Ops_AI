from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.draft import DraftStatus


class SourceCitation(BaseModel):
    document_id: int
    document_title: str
    chunk_index: int
    content_snippet: str
    score: Optional[float] = None


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    success: bool = True


class ResponseDraftCreate(BaseModel):
    draft_body: str
    rationale: Optional[str] = None
    retrieved_sources: List[Dict[str, Any]] = []
    tool_calls_used: List[Dict[str, Any]] = []


class ResponseDraftReview(BaseModel):
    status: DraftStatus  # approved, rejected, edited_and_approved
    edited_draft_body: Optional[str] = None
    reviewed_by: str = Field(default="Staff Reviewer")
    review_feedback: Optional[str] = None


class ResponseDraftResponse(BaseModel):
    id: int
    enquiry_id: int
    draft_body: str
    rationale: Optional[str] = None
    retrieved_sources: List[Dict[str, Any]] = []
    tool_calls_used: List[Dict[str, Any]] = []
    status: DraftStatus
    order_product_mismatch: bool = False
    mismatch_details: Optional[Dict[str, Any]] = None
    answerability_details: Optional[Dict[str, Any]] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_feedback: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
