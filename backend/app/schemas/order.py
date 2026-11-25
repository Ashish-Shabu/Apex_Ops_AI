from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class OrderItemResponse(BaseModel):
    id: int
    sku: str
    product_name: str
    quantity: int
    unit_price: float

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    order_number: str
    customer_name: str
    customer_email: str
    status: str
    total_amount: float
    currency: str
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    shipping_address: str
    order_date: datetime
    estimated_delivery: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    items: List[OrderItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class OrderLookupRequest(BaseModel):
    order_number: Optional[str] = None
    customer_email: Optional[str] = None
