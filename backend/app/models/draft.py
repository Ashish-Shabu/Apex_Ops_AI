import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SAEnum, JSON, Boolean
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class DraftStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED_AND_APPROVED = "edited_and_approved"


class ResponseDraft(Base):
    __tablename__ = "response_drafts"

    id = Column(Integer, primary_key=True, index=True)
    enquiry_id = Column(Integer, ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=False, index=True)
    
    draft_body = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    retrieved_sources = Column(JSON, default=list)  # list of chunk citations
    tool_calls_used = Column(JSON, default=list)    # list of tools executed (e.g. order lookup)
    
    status = Column(SAEnum(DraftStatus), default=DraftStatus.PENDING_REVIEW, nullable=False, index=True)
    order_product_mismatch = Column(Boolean, default=False, nullable=False)
    mismatch_details = Column(JSON, default=dict)
    answerability_details = Column(JSON, default=dict)
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_feedback = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    enquiry = relationship("Enquiry", back_populates="drafts")
