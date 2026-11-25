import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from backend.app.core.logging import logger


# Common product categories and lexical keywords recognized in customer support
PRODUCT_TAXONOMY = {
    "keyboard": [
        "keyboard", "keyboards", "mechanical keyboard", "wireless keyboard",
        "switches", "switch", "keycap", "keycaps"
    ],
    "chair": [
        "chair", "chairs", "desk chair", "mesh chair", "ergonomic chair",
        "office chair", "seating", "armrest"
    ],
    "headset": [
        "headset", "headsets", "headphones", "headphone", "earphones",
        "earbuds", "audio", "mic", "microphone", "anc"
    ],
    "webcam": [
        "webcam", "webcams", "camera", "cameras", "streamview", "video cam"
    ],
    "mouse": [
        "mouse", "mice", "trackpad", "optical mouse"
    ],
    "monitor": [
        "monitor", "monitors", "display", "screen"
    ],
    "desk": [
        "standing desk", "desk", "workstation", "table"
    ]
}


class OrderValidationResult(BaseModel):
    is_validated: bool = False
    has_mismatch: bool = False
    is_match: bool = False
    customer_mentioned_terms: List[str] = []
    order_number: Optional[str] = None
    order_actual_products: List[str] = []
    matching_products: List[str] = []
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mismatch_detected": self.has_mismatch,
            "is_match": self.is_match,
            "order_number": self.order_number,
            "customer_mentioned_terms": self.customer_mentioned_terms,
            "order_actual_products": self.order_actual_products,
            "matching_products": self.matching_products,
            "reason": self.reason
        }


def extract_product_terms_from_text(text: str) -> List[str]:
    """
    Extract product keywords and categories mentioned in customer text.
    """
    if not text:
        return []

    lower_text = text.lower()
    found_categories = set()
    found_terms = []

    # Check taxonomy matches
    for category, keywords in PRODUCT_TAXONOMY.items():
        for kw in keywords:
            # Word boundary regex search
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, lower_text):
                if category not in found_categories:
                    found_categories.add(category)
                    found_terms.append(kw)
                break

    return found_terms


def validate_order_products(
    enquiry_subject: str,
    enquiry_message: str,
    order: Optional[Dict[str, Any]]
) -> OrderValidationResult:
    """
    Backend validation logic strictly comparing products mentioned in the customer enquiry
    against actual items returned by the order lookup tool.
    Never relies solely on the LLM to verify order consistency.
    """
    combined_text = f"{enquiry_subject} {enquiry_message}".strip()
    mentioned_terms = extract_product_terms_from_text(combined_text)

    # If no order record is available
    if not order:
        return OrderValidationResult(
            is_validated=False,
            has_mismatch=False,
            is_match=False,
            customer_mentioned_terms=mentioned_terms,
            reason="Order record is not available or not found."
        )

    order_num = order.get("order_number")
    items = order.get("items", [])
    order_product_names = [it.get("product_name", "") for it in items if it.get("product_name")]

    # If customer did NOT mention any specific product (e.g. general "Where is my order?")
    if not mentioned_terms:
        return OrderValidationResult(
            is_validated=True,
            has_mismatch=False,
            is_match=True,
            order_number=order_num,
            customer_mentioned_terms=[],
            order_actual_products=order_product_names,
            matching_products=order_product_names,
            reason="Customer did not specify a product name; general order query."
        )

    # Check each mentioned term against order items
    matching_items = []
    for term in mentioned_terms:
        # Identify the taxonomy category for this term
        matched_cat = None
        for cat, kws in PRODUCT_TAXONOMY.items():
            if term in kws:
                matched_cat = cat
                break

        for prod_name in order_product_names:
            lower_prod = prod_name.lower()
            # Direct keyword match
            if term in lower_prod:
                if prod_name not in matching_items:
                    matching_items.append(prod_name)
            # Taxonomy category match (e.g. customer said "keyboard", order has "Apex Pro Wireless Mechanical Keyboard")
            elif matched_cat:
                cat_keywords = PRODUCT_TAXONOMY.get(matched_cat, [])
                if any(re.search(r'\b' + re.escape(kw) + r'\b', lower_prod) for kw in cat_keywords):
                    if prod_name not in matching_items:
                        matching_items.append(prod_name)

    # Determine match vs mismatch
    if matching_items:
        logger.info(
            f"Order validation SUCCESS for {order_num}: Customer mentioned {mentioned_terms} matches {matching_items}"
        )
        return OrderValidationResult(
            is_validated=True,
            has_mismatch=False,
            is_match=True,
            order_number=order_num,
            customer_mentioned_terms=mentioned_terms,
            order_actual_products=order_product_names,
            matching_products=matching_items,
            reason=f"Matched product '{matching_items[0]}' in order {order_num}."
        )
    else:
        reason = (
            f"Product mismatch detected: Customer enquiry refers to '{', '.join(mentioned_terms)}', "
            f"but order {order_num} contains: '{', '.join(order_product_names)}'."
        )
        logger.warning(f"Order validation MISMATCH: {reason}")
        return OrderValidationResult(
            is_validated=True,
            has_mismatch=True,
            is_match=False,
            order_number=order_num,
            customer_mentioned_terms=mentioned_terms,
            order_actual_products=order_product_names,
            matching_products=[],
            reason=reason
        )
