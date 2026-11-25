import json
from unittest.mock import MagicMock, patch
import pytest
from google.genai import types, errors

from backend.app.core.config import Settings
from backend.app.services.ai.llm_client import LLMClient
from backend.app.services.ai.embeddings import get_embeddings, _get_gemini_embeddings


def test_provider_selection_logic():
    """Verify provider selection logic based on keys and provider settings."""
    # 1. Gemini enabled with key
    s1 = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="test_gemini_key", OPENAI_API_KEY="")
    assert s1.active_provider == "gemini"
    assert s1.is_demo_mode is False

    # 2. Gemini selected but no key -> fallback to demo
    s2 = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="", OPENAI_API_KEY="")
    assert s2.active_provider == "demo"
    assert s2.is_demo_mode is True

    # 3. OpenAI selected with key
    s3 = Settings(LLM_PROVIDER="openai", GEMINI_API_KEY="", OPENAI_API_KEY="test_openai_key")
    assert s3.active_provider == "openai"
    assert s3.is_demo_mode is False

    # 4. Explicit demo provider
    s4 = Settings(LLM_PROVIDER="demo", GEMINI_API_KEY="test_key", OPENAI_API_KEY="test_key")
    assert s4.active_provider == "demo"
    assert s4.is_demo_mode is True


def test_mocked_gemini_classification():
    """Verify Gemini classification with mocked google-genai response."""
    mock_response_json = {
        "category": "delivery",
        "priority": "high",
        "sentiment": "frustrated",
        "summary": "Customer Alice Smith is asking for urgent delivery update for order ORD-1002.",
        "order_number_detected": "ORD-1002",
        "key_entities": ["keyboard", "tracking", "ORD-1002"],
        "confidence": 0.98
    }

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(mock_response_json)
    mock_client.models.generate_content.return_value = mock_resp

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        client = LLMClient()
        result = client.classify_and_summarize(
            customer_name="Alice Smith",
            subject="Where is my shipment?",
            message="Hi, I ordered ORD-1002 and tracking has not moved in 3 days."
        )

        assert result["category"] == "delivery"
        assert result["priority"] == "high"
        assert result["sentiment"] == "frustrated"
        assert result["order_number_detected"] == "ORD-1002"
        assert result["provider"] == "gemini"
        assert result["is_demo_mode"] is False
        assert mock_client.models.generate_content.called


def test_mocked_gemini_draft_generation_with_tool_calling(db_session):
    """Verify Gemini draft generation with simulated function call and order lookup."""
    mock_client = MagicMock()

    # Pass 1: Gemini decides to call lookup_order
    mock_call = MagicMock()
    mock_call.name = "lookup_order"
    mock_call.args = {"order_number": "ORD-1002"}

    mock_resp_pass1 = MagicMock()
    mock_resp_pass1.function_calls = [mock_call]

    # Pass 2: Gemini synthesizes final JSON draft grounded in tool result
    mock_resp_pass2 = MagicMock()
    mock_resp_pass2.text = json.dumps({
        "draft_body": "Dear Alice, your order ORD-1002 is currently in transit with DHL Express.",
        "rationale": "Grounded in lookup_order result for ORD-1002 and Shipping Policy."
    })

    mock_client.models.generate_content.side_effect = [mock_resp_pass1, mock_resp_pass2]

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        client = LLMClient()
        enquiry_data = {
            "customer_name": "Alice Smith",
            "customer_email": "alice@example.com",
            "subject": "Order status",
            "message": "Can you check status for ORD-1002?",
            "category": "delivery",
            "order_number": "ORD-1002"
        }
        retrieved_chunks = [{
            "document_id": 1,
            "document_title": "Shipping Guidelines",
            "chunk_index": 0,
            "content": "Deliveries take 3-5 business days."
        }]

        result = client.generate_response_draft(
            enquiry_data=enquiry_data,
            retrieved_chunks=retrieved_chunks,
            has_sufficient_knowledge=True,
            db=db_session
        )

        assert "ORD-1002" in result["draft_body"]
        assert result["provider"] == "gemini"
        assert result["is_demo_mode"] is False
        assert len(result["tools_executed"]) == 1
        assert result["tools_executed"][0]["tool_name"] == "lookup_order"
        assert result["tools_executed"][0]["result"]["found"] is True
        assert result["order_product_mismatch"] is False


def test_mocked_gemini_draft_generation_with_mismatch(db_session):
    """Verify Gemini draft generation handles and flags order-product mismatch."""
    mock_client = MagicMock()

    # Pass 1: Gemini calls lookup_order for ORD-1001 (which is a Chair)
    mock_call = MagicMock()
    mock_call.name = "lookup_order"
    mock_call.args = {"order_number": "ORD-1001"}

    mock_resp_pass1 = MagicMock()
    mock_resp_pass1.function_calls = [mock_call]

    # Pass 2: Synthesis response respecting the backend validation alert
    mock_resp_pass2 = MagicMock()
    mock_resp_pass2.text = json.dumps({
        "draft_body": "Dear Customer, order ORD-1001 is registered for an Apex Ergonomic Mesh Desk Chair, which differs from the wireless keyboard you mentioned. Please verify your order number.",
        "rationale": "Flagged product mismatch between keyboard and chair."
    })

    mock_client.models.generate_content.side_effect = [mock_resp_pass1, mock_resp_pass2]

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        client = LLMClient()
        enquiry_data = {
            "customer_name": "Marcus",
            "customer_email": "marcus@example.com",
            "subject": "Keyboard issue",
            "message": "I ordered a wireless keyboard. It stopped working. Order ORD-1001.",
            "category": "refund_return",
            "order_number": "ORD-1001"
        }

        result = client.generate_response_draft(
            enquiry_data=enquiry_data,
            retrieved_chunks=[],
            has_sufficient_knowledge=False,
            db=db_session
        )

        assert result["order_product_mismatch"] is True
        assert result["mismatch_details"] is not None
        assert result["mismatch_details"]["mismatch_detected"] is True
        # Verify customer-facing draft does NOT reveal the actual product (Chair)
        assert "Chair" not in result["draft_body"]
        assert "Desk Chair" not in result["draft_body"]
        assert "Apex Ergonomic Mesh Desk Chair" not in result["draft_body"]
        assert "could not be verified" in result["draft_body"].lower() or "verify" in result["draft_body"].lower()
        # Verify internal diagnostic details are preserved for authorized staff
        assert "Chair" in result["mismatch_details"]["order_actual_products"][0]
        assert "Chair" in result["rationale"]


def test_mocked_gemini_embeddings():
    """Verify Gemini text-embedding-004 integration with mocked output_dimensionality."""
    mock_client = MagicMock()
    
    # 384-dimensional mock vector
    dummy_vector = [0.05] * 384
    mock_embedding = types.ContentEmbedding(values=dummy_vector)
    mock_resp = types.EmbedContentResponse(embeddings=[mock_embedding, mock_embedding])
    mock_client.models.embed_content.return_value = mock_resp

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("backend.app.core.config.settings.EMBEDDING_DIMENSION", 384), \
         patch("google.genai.Client", return_value=mock_client):

        vectors = get_embeddings(["Return policy query", "Shipping timeframe query"])
        assert len(vectors) == 2
        assert len(vectors[0]) == 384
        assert len(vectors[1]) == 384
        assert mock_client.models.embed_content.called


def test_gemini_api_error_graceful_fallback():
    """Verify that Gemini quota errors or API failures gracefully fall back to deterministic demo mode."""
    mock_client = MagicMock()
    # Simulate API quota/rate limit error
    mock_client.models.generate_content.side_effect = Exception("ResourceExhausted: 429 Resource has been exhausted")

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        client = LLMClient()
        # Should NOT raise, but return deterministic fallback
        result = client.classify_and_summarize(
            customer_name="David Wilson",
            subject="Need refund for damaged item",
            message="Item arrived broken, need refund immediately."
        )

        assert result is not None
        assert result["category"] == "refund_return"
        assert result["is_demo_mode"] is True
        assert "Deterministic" in result.get("engine", "")
