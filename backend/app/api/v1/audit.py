from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.database import get_db
from backend.app.models.audit import AuditLog
from backend.app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit History"])


@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    enquiry_id: Optional[int] = None,
    action: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List system and staff audit trail logs."""
    query = db.query(AuditLog)
    if enquiry_id:
        query = query.filter(AuditLog.enquiry_id == enquiry_id)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit).all()
