import pytest
from fastapi.testclient import TestClient
from backend.app.services.ai.order_validator import (
    validate_order_products,
    extract_product_terms_from_text,
    OrderValidationResult
)
from backend.app.services.ai.llm_client import LLMClient
from backend.app.models.audit import AuditLog


def test_extract_product_terms():
    """Verify keyword and taxonomy extraction from customer text."""
    terms1 = extract_product_terms_from_text("I ordered a wireless keyboard. It stopped working.")
    assert "keyboard" in terms1 or "wireless keyboard" in terms1

    terms2 = extract_product_terms_from_text("Where is my order ORD-1001?")
    assert len(terms2) == 0

    terms3 = extract_product_terms_from_text("The mesh chair armrest is loose and webcam is blurry.")
    assert len(terms3) >= 2


def test_matching_product_and_order():
    """Requirement 8.1: Test matching product and order."""
    order_data = {
        "order_number": "ORD-1002",
        "status": "in_transit",
        "items": [
            {"product_name": "Apex Pro Wireless Mechanical Keyboard", "sku": "KB-MECH-W"}
        ]
    }
    subject = "Where is my keyboard?"
    message = "I ordered a wireless keyboard under ORD-1002. Please check delivery."

    result = validate_order_products(subject, message, order_data)

    assert result.is_validated is True
    assert result.has_mismatch is False
    assert result.is_match is True
    assert len(result.matching_products) == 1
    assert "Keyboard" in result.matching_products[0]


def test_mismatching_product_and_order():
    """
    Requirement 8.2: Test mismatching product and order.
    The exact customer issue reported:
    Customer: 'I ordered a wireless keyboard... ORD-1001'
    Order ORD-1001 is for 'Apex Ergonomic Mesh Desk Chair'.
    """
    order_data = {
        "order_number": "ORD-1001",
        "status": "delivered",
        "items": [
            {"product_name": "Apex Ergonomic Mesh Desk Chair", "sku": "CHAIR-ERG-01"}
        ]
    }
    subject = "Keyboard stopped working"
    message = "I ordered a wireless keyboard. It has suddenly stopped working. My order number is ORD-1001."

    result = validate_order_products(subject, message, order_data)

    assert result.is_validated is True
    assert result.has_mismatch is True
    assert result.is_match is False
    assert len(result.customer_mentioned_terms) > 0
    assert "Chair" in result.order_actual_products[0]
    assert "mismatch" in result.reason.lower()


def test_missing_order_number():
    """Requirement 8.3: Test missing order number (no order record)."""
    subject = "Question about keyboard warranty"
    message = "I ordered a wireless keyboard but do not have my order number handy."

    result = validate_order_products(subject, message, None)

    assert result.is_validated is False
    assert result.has_mismatch is False
    assert result.is_match is False
    assert "keyboard" in result.customer_mentioned_terms


def test_order_not_found():
    """Requirement 8.4: Test order not found in database."""
    subject = "Where is ORD-9999"
    message = "I bought a webcam under order ORD-9999. Status please."

    # lookup_order returns None / found=False
    result = validate_order_products(subject, message, None)

    assert result.is_validated is False
    assert result.has_mismatch is False
    assert result.is_match is False


def test_multiple_products_in_one_order():
    """Requirement 8.5: Test multiple products in one order."""
    multi_order = {
        "order_number": "ORD-5000",
        "status": "shipped",
        "items": [
            {"product_name": "Apex Ergonomic Mesh Desk Chair", "sku": "CHAIR-ERG-01"},
            {"product_name": "Apex Pro Wireless Mechanical Keyboard", "sku": "KB-MECH-W"}
        ]
    }

    # Sub-case A: Customer asks about keyboard -> MATCH because keyboard is in the order
    res_match = validate_order_products(
        "Wireless keyboard defective",
        "The keyboard from my order ORD-5000 has stopped typing.",
        multi_order
    )
    assert res_match.is_validated is True
    assert res_match.has_mismatch is False
    assert res_match.is_match is True
    assert len(res_match.matching_products) == 1
    assert "Keyboard" in res_match.matching_products[0]

    # Sub-case B: Customer asks about webcam -> MISMATCH because webcam is NOT in order [Chair, Keyboard]
    res_mismatch = validate_order_products(
        "Webcam issue",
        "My 4K webcam from order ORD-5000 is blurry.",
        multi_order
    )
    assert res_mismatch.is_validated is True
    assert res_mismatch.has_mismatch is True
    assert res_mismatch.is_match is False
    assert len(res_mismatch.matching_products) == 0
    assert len(res_mismatch.order_actual_products) == 2


def test_mismatch_end_to_end_draft_and_audit(client: TestClient, db_session):
    """
    End-to-end integration test:
    1. Create enquiry mentioning keyboard with ORD-1001 (Chair).
    2. Generate draft.
    3. Verify order_product_mismatch is True in draft.
    4. Verify draft asks customer to verify order number and does NOT claim chair is keyboard.
    5. Verify audit log records order_product_mismatch_flagged.
    """
    enquiry_payload = {
        "customer_name": "Jonathan Grey",
        "customer_email": "jonathan@example.com",
        "channel": "email",
        "subject": "Wireless keyboard stopped working",
        "message": "I ordered a wireless keyboard. It has suddenly stopped working. My order number is ORD-1001.",
        "order_number": "ORD-1001"
    }
    create_resp = client.post("/api/v1/enquiries", json=enquiry_payload)
    assert create_resp.status_code == 201
    enquiry_id = create_resp.json()["id"]

    # Generate draft
    draft_resp = client.post(f"/api/v1/enquiries/{enquiry_id}/draft", json={})
    assert draft_resp.status_code == 200
    draft_data = draft_resp.json()

    # Verify structured mismatch flags (Requirement 6)
    assert draft_data["order_product_mismatch"] is True
    assert draft_data["mismatch_details"] is not None
    assert draft_data["mismatch_details"]["mismatch_detected"] is True
    assert draft_data["mismatch_details"]["order_number"] == "ORD-1001"

    # Verify customer-facing draft does NOT reveal the other product (Chair)
    draft_body = draft_data["draft_body"]
    assert "ORD-1001" in draft_body
    assert "Chair" not in draft_body
    assert "Desk Chair" not in draft_body
    assert "Apex Ergonomic Mesh Desk Chair" not in draft_body
    assert "could not be verified" in draft_body.lower() or "verify" in draft_body.lower()

    # Verify internal staff details preserve the actual product for internal diagnosis
    assert "Chair" in draft_data["mismatch_details"]["order_actual_products"][0]
    assert "Chair" in draft_data["rationale"]

    # Verify audit log recorded mismatch details for internal investigation (Requirement 5)
    detail_resp = client.get(f"/api/v1/enquiries/{enquiry_id}")
    assert detail_resp.status_code == 200
    enquiry_detail = detail_resp.json()
    audit_actions = [log["action"] for log in enquiry_detail["audit_logs"]]
    assert "order_product_mismatch_flagged" in audit_actions
    mismatch_log = next(log for log in enquiry_detail["audit_logs"] if log["action"] == "order_product_mismatch_flagged")
    assert "Chair" in str(mismatch_log["details"])
