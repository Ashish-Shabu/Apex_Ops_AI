import io
from fastapi.testclient import TestClient


def test_list_documents(client: TestClient):
    resp = client.get("/api/v1/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) >= 3


def test_upload_txt_document(client: TestClient):
    content = "FAQ: International shipping takes 7 to 10 days. Customs duties may apply at border clearance."
    file_tuple = ("intl_shipping_faq.txt", io.BytesIO(content.encode("utf-8")), "text/plain")
    
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": file_tuple},
        data={"title": "International Shipping FAQ"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "International Shipping FAQ"
    assert data["chunk_count"] >= 1
    assert len(data["chunks"]) >= 1


def test_semantic_search_rag(client: TestClient):
    search_payload = {
        "query": "How many days do I have to return an item for refund?",
        "top_k": 3
    }
    resp = client.post("/api/v1/documents/search", json=search_payload)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) > 0
    # Top result should be return policy
    top_doc = results[0]
    assert "Return" in top_doc["document_title"]
    assert top_doc["similarity_score"] > 0.3
