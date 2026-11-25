from typing import Dict, List, Any
from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_enquiries: int
    pending_enquiries: int
    awaiting_approval_enquiries: int
    resolved_enquiries: int
    categories_breakdown: Dict[str, int]
    priorities_breakdown: Dict[str, int]
    total_documents: int
    total_chunks: int
    recent_activity: List[Dict[str, Any]]
