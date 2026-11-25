from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.audit import AuditLog
from backend.app.core.logging import logger


def record_audit_log(
    db: Session,
    action: str,
    actor: str,
    enquiry_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """Record an audit trail event."""
    log_entry = AuditLog(
        enquiry_id=enquiry_id,
        action=action,
        actor=actor,
        details=details or {}
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"Audit event recorded: [{action}] by [{actor}] for enquiry {enquiry_id}")
    return log_entry
