from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from backend.app.core.database import get_db
from backend.app.models.enquiry import Enquiry, EnquiryStatus, EnquiryCategory, EnquiryPriority
from backend.app.models.document import Document, DocumentChunk
from backend.app.models.audit import AuditLog
from backend.app.schemas.analytics import DashboardStats

router = APIRouter(prefix="/analytics", tags=["Dashboard & Analytics"])


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Aggregate KPI metrics for customer operations dashboard."""
    total_enquiries = db.query(Enquiry).count()
    pending = db.query(Enquiry).filter(Enquiry.status == EnquiryStatus.PENDING).count()
    awaiting = db.query(Enquiry).filter(Enquiry.status == EnquiryStatus.AWAITING_APPROVAL).count()
    resolved = db.query(Enquiry).filter(Enquiry.status == EnquiryStatus.RESOLVED).count()

    # Category breakdown
    cat_counts = (
        db.query(Enquiry.category, func.count(Enquiry.id))
        .group_by(Enquiry.category)
        .all()
    )
    categories_dict = {cat.value if hasattr(cat, "value") else str(cat): count for cat, count in cat_counts}

    # Priority breakdown
    prio_counts = (
        db.query(Enquiry.priority, func.count(Enquiry.id))
        .group_by(Enquiry.priority)
        .all()
    )
    priorities_dict = {prio.value if hasattr(prio, "value") else str(prio): count for prio, count in prio_counts}

    total_docs = db.query(Document).count()
    total_chunks = db.query(DocumentChunk).count()

    # Recent activity stream
    recent_logs = db.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(10).all()
    recent_activity = [
        {
            "id": l.id,
            "action": l.action,
            "actor": l.actor,
            "enquiry_id": l.enquiry_id,
            "details": l.details or {},
            "created_at": l.created_at.isoformat()
        }
        for l in recent_logs
    ]

    return DashboardStats(
        total_enquiries=total_enquiries,
        pending_enquiries=pending,
        awaiting_approval_enquiries=awaiting,
        resolved_enquiries=resolved,
        categories_breakdown=categories_dict,
        priorities_breakdown=priorities_dict,
        total_documents=total_docs,
        total_chunks=total_chunks,
        recent_activity=recent_activity
    )
