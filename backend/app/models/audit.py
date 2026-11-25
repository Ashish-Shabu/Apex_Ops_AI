from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    enquiry_id = Column(Integer, ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(100), nullable=False)  # enquiry_created, ai_classified, draft_generated, draft_approved, etc.
    actor = Column(String(100), nullable=False)   # system, ai_assistant, staff:<name>
    details = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    enquiry = relationship("Enquiry", back_populates="audit_logs")
