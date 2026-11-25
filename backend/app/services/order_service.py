from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.app.models.order import Order, OrderItem
from backend.app.core.logging import logger


def get_order_by_number(db: Session, order_number: str) -> Optional[Dict[str, Any]]:
    """
    Safely retrieve order details by order_number using parameterized ORM query.
    Never executes raw or untrusted SQL.
    """
    cleaned_number = order_number.strip().upper()
    order = db.query(Order).filter(Order.order_number == cleaned_number).first()
    if not order:
        # Try case-insensitive fallback
        order = db.query(Order).filter(Order.order_number.ilike(f"%{cleaned_number}%")).first()

    if not order:
        return None

    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "status": order.status,
        "total_amount": order.total_amount,
        "currency": order.currency,
        "tracking_number": order.tracking_number,
        "carrier": order.carrier,
        "shipping_address": order.shipping_address,
        "order_date": order.order_date.isoformat() if order.order_date else None,
        "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "items": [
            {
                "sku": item.sku,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in order.items
        ]
    }


def search_orders_by_customer(db: Session, query: str) -> List[Dict[str, Any]]:
    """
    Safely search orders by customer email or name.
    """
    cleaned_query = query.strip()
    orders = db.query(Order).filter(
        or_(
            Order.customer_email.ilike(f"%{cleaned_query}%"),
            Order.customer_name.ilike(f"%{cleaned_query}%"),
            Order.order_number.ilike(f"%{cleaned_query}%")
        )
    ).limit(5).all()

    results = []
    for order in orders:
        results.append({
            "order_number": order.order_number,
            "customer_name": order.customer_name,
            "customer_email": order.customer_email,
            "status": order.status,
            "total_amount": order.total_amount,
            "order_date": order.order_date.isoformat() if order.order_date else None,
            "items_count": len(order.items)
        })
    return results
