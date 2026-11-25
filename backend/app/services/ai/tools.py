from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.services.order_service import get_order_by_number, search_orders_by_customer
from backend.app.core.logging import logger

AVAILABLE_TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Look up complete order details (status, tracking, items, address, delivery date) using an order number (e.g. ORD-1001).",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_number": {
                        "type": "string",
                        "description": "The exact or partial order reference number (e.g., ORD-1001, 1001)"
                    }
                },
                "required": ["order_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_customer_orders",
            "description": "Find recent orders associated with a customer's email address or name when the order number is not provided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Customer email or full name to search for"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Controlled tool executor.
    Guarantees no arbitrary code or SQL execution.
    Only strictly registered functions are executed.
    """
    logger.info(f"Executing tool '{tool_name}' with arguments: {arguments}")
    
    if tool_name == "lookup_order":
        order_num = arguments.get("order_number", "")
        if not order_num:
            return {"error": "Missing 'order_number' parameter"}
        
        result = get_order_by_number(db, str(order_num))
        if result:
            return {
                "found": True,
                "order": result
            }
        else:
            return {
                "found": False,
                "message": f"No order found matching order number '{order_num}'."
            }

    elif tool_name == "search_customer_orders":
        query = arguments.get("query", "")
        if not query:
            return {"error": "Missing 'query' parameter"}
        
        results = search_orders_by_customer(db, str(query))
        return {
            "count": len(results),
            "orders": results
        }

    else:
        return {"error": f"Unknown tool '{tool_name}'."}
