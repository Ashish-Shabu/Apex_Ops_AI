from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int
    enquiry_id: Optional[int] = None
    action: str
    actor: str
    details: Dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
