import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SAEnum, Float, JSON
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class EnquiryStatus(str, enum.Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class EnquiryCategory(str, enum.Enum):
    ORDER_STATUS = "order_status"
    DELIVERY = "delivery"
    REFUND_RETURN = "refund_return"
    COMPANY_POLICY = "company_policy"
    GENERAL_SUPPORT = "general_support"


class EnquiryPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Enquiry(Base):
    __tablename__ = "enquiries"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), nullable=False, index=True)
    channel = Column(String(50), default="email")
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    category = Column(SAEnum(EnquiryCategory), default=EnquiryCategory.GENERAL_SUPPORT, nullable=False)
    status = Column(SAEnum(EnquiryStatus), default=EnquiryStatus.PENDING, nullable=False, index=True)
    priority = Column(SAEnum(EnquiryPriority), default=EnquiryPriority.MEDIUM, nullable=False)
    
    sentiment = Column(String(50), default="neutral")
    ai_summary = Column(Text, nullable=True)
    ai_confidence = Column(Float, default=0.0)
    order_number = Column(String(100), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    drafts = relationship("ResponseDraft", back_populates="enquiry", cascade="all, delete-orphan", order_by="desc(ResponseDraft.created_at)")
    audit_logs = relationship("AuditLog", back_populates="enquiry", cascade="all, delete-orphan", order_by="desc(AuditLog.created_at)")
