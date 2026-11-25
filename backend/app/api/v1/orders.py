from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.database import get_db
from backend.app.models.order import Order
from backend.app.schemas.order import OrderResponse, OrderLookupRequest
from backend.app.services.order_service import get_order_by_number, search_orders_by_customer

router = APIRouter(prefix="/orders", tags=["Order Tools & Management"])


@router.get("", response_model=List[OrderResponse])
def list_orders(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50)
):
    """List sample e-commerce orders for operations and testing."""
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    return query.order_by(desc(Order.order_date)).offset(skip).limit(limit).all()


@router.get("/{order_number}", response_model=OrderResponse)
def get_order(order_number: str, db: Session = Depends(get_db)):
    """Retrieve detailed order information by order number."""
    order_data = get_order_by_number(db, order_number)
    if not order_data:
        raise HTTPException(status_code=404, detail=f"Order '{order_number}' not found")
    
    order = db.query(Order).filter(Order.order_number == order_data["order_number"]).first()
    return order


@router.post("/lookup")
def lookup_order_tool_endpoint(req: OrderLookupRequest, db: Session = Depends(get_db)):
    """
    Direct endpoint testing the controlled order lookup tool used by the LLM.
    Guarantees parameterized execution with no arbitrary SQL.
    """
    if req.order_number:
        result = get_order_by_number(db, req.order_number)
        if not result:
            return {"found": False, "message": f"No order found matching '{req.order_number}'"}
        return {"found": True, "order": result}
    elif req.customer_email:
        results = search_orders_by_customer(db, req.customer_email)
        return {"found": len(results) > 0, "count": len(results), "orders": results}
    else:
        raise HTTPException(status_code=400, detail="Provide either order_number or customer_email")
