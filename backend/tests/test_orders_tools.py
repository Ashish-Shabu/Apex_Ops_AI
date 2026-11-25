from fastapi.testclient import TestClient


def test_list_orders(client: TestClient):
    resp = client.get("/api/v1/orders")
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) >= 4


def test_order_lookup_tool_by_number(client: TestClient):
    resp = client.post("/api/v1/orders/lookup", json={"order_number": "ORD-1001"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["order"]["customer_name"] == "John Doe"
    assert data["order"]["status"] == "delivered"
    assert len(data["order"]["items"]) == 1


def test_order_lookup_tool_not_found(client: TestClient):
    resp = client.post("/api/v1/orders/lookup", json={"order_number": "ORD-9999"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False


def test_dashboard_analytics(client: TestClient):
    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    stats = resp.json()
    assert "total_enquiries" in stats
    assert "pending_enquiries" in stats
    assert "awaiting_approval_enquiries" in stats
    assert "resolved_enquiries" in stats
    assert "categories_breakdown" in stats
    assert len(stats["recent_activity"]) > 0
