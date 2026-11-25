import pytest
from fastapi.testclient import TestClient


def test_list_enquiries(client: TestClient):
    resp = client.get("/api/v1/enquiries")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_create_enquiry_with_auto_classification(client: TestClient):
    payload = {
        "customer_name": "Samantha Reed",
        "customer_email": "samantha@example.com",
        "channel": "email",
        "subject": "Need to return keyboard ORD-1002",
        "message": "Hello, the keyboard switches are too loud for my office. I need to return it under order ORD-1002.",
        "order_number": None
    }
    resp = client.post("/api/v1/enquiries", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["customer_name"] == "Samantha Reed"
    assert data["category"] == "refund_return"
    assert data["order_number"] == "ORD-1002"
    assert data["status"] == "pending"
    assert data["ai_summary"] is not None
    assert len(data["audit_logs"]) >= 2


def test_generate_draft_and_review_workflow(client: TestClient):
    # 1. Create enquiry
    payload = {
        "customer_name": "Marcus Vance",
        "customer_email": "marcus.vance@example.com",
        "channel": "web_chat",
        "subject": "Delivery update on ORD-1001",
        "message": "When will my chair arrive? Order reference is ORD-1001.",
        "order_number": "ORD-1001"
    }
    create_resp = client.post("/api/v1/enquiries", json=payload)
    assert create_resp.status_code == 201
    enquiry_id = create_resp.json()["id"]

    # 2. Generate Draft (invokes RAG + lookup_order tool)
    draft_resp = client.post(f"/api/v1/enquiries/{enquiry_id}/draft", json={"staff_notes": "Expedite customer note."})
    assert draft_resp.status_code == 200
    draft_data = draft_resp.json()
    assert draft_data["status"] == "pending_review"
    assert "ORD-1001" in draft_data["draft_body"]
    assert len(draft_data["tool_calls_used"]) > 0

    draft_id = draft_data["id"]

    # 3. Staff Approve Draft
    review_resp = client.post(
        f"/api/v1/enquiries/{enquiry_id}/drafts/{draft_id}/review",
        json={
            "status": "approved",
            "reviewed_by": "Senior Agent Clara",
            "review_feedback": "Looks great and factual."
        }
    )
    assert review_resp.status_code == 200
    reviewed_data = review_resp.json()
    assert reviewed_data["status"] == "approved"
    assert reviewed_data["reviewed_by"] == "Senior Agent Clara"

    # 4. Verify enquiry status transitioned to resolved
    get_resp = client.get(f"/api/v1/enquiries/{enquiry_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "resolved"
