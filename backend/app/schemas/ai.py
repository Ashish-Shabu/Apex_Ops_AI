from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.models.enquiry import EnquiryCategory, EnquiryPriority


class AIClassificationResult(BaseModel):
    category: EnquiryCategory
    priority: EnquiryPriority
    sentiment: str = Field(description="positive, neutral, frustrated, or angry")
    summary: str = Field(description="Concise 1-2 sentence summary of the customer enquiry")
    order_number_detected: Optional[str] = Field(None, description="Extracted order number if mentioned in message")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    key_entities: List[str] = Field(default_factory=list, description="Key items, dates, tracking codes mentioned")


class AIDraftGenerationRequest(BaseModel):
    staff_notes: Optional[str] = None
    force_order_lookup: Optional[str] = None


class AIDraftGenerationResult(BaseModel):
    draft_body: str
    rationale: str
    sources_used: List[Dict[str, Any]] = []
    tools_executed: List[Dict[str, Any]] = []
    is_demo_mode: bool = False
    provider: Optional[str] = None
    order_product_mismatch: bool = False
    mismatch_details: Optional[Dict[str, Any]] = None
    warning: Optional[str] = None
