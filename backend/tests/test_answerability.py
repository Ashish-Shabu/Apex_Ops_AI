import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.enquiry import Enquiry, EnquiryStatus
from backend.app.models.audit import AuditLog
from backend.app.services.ai.answerability import (
    verify_answerability,
    AnswerabilityResult,
    ANSWERABILITY_CONFIDENCE_THRESHOLD
)


# =====================================================================
# 1. RELEVANT CHUNKS THAT GENUINELY ANSWER A QUESTION
# =====================================================================

def test_answerability_relevant_chunks_gemini_mock():
    """Verify Gemini answerability verification returns answerable=True and supporting chunks when evidence directly answers."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "answerable": True,
        "confidence": 0.94,
        "supporting_chunk_indices": [0],
        "reason": "Chunk 0 explicitly states the 30 calendar day return eligibility window."
    })
    mock_client.models.generate_content.return_value = mock_resp

    chunks = [
        {
            "chunk_id": 1,
            "document_title": "Customer Return and Refund Policy",
            "chunk_index": 0,
            "similarity_score": 0.78,
            "content": "Customers may request a return within 30 calendar days from the confirmed delivery date."
        },
        {
            "chunk_id": 5,
            "document_title": "Shipping and Delivery Guidelines",
            "chunk_index": 0,
            "similarity_score": 0.52,
            "content": "Standard in-stock orders are processed within 24 to 48 business hours."
        }
    ]

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        result = verify_answerability("How many days do I have to return an item?", chunks)

    assert isinstance(result, AnswerabilityResult)
    assert result.answerable is True
    assert result.confidence == 0.94
    assert result.requires_human_review is False
    assert len(result.supporting_chunks) == 1
    assert result.supporting_chunks[0]["chunk_id"] == 1
    assert result.verification_provider == "gemini"


# =====================================================================
# 2. SEMANTICALLY RELATED CHUNKS THAT DO NOT ANSWER THE QUESTION
# =====================================================================

def test_answerability_semantically_related_but_unanswerable():
    """
    Verify that topic-adjacent chunks (e.g. continental shipping for a German VAT question)
    are rejected with answerable=False and requires_human_review=True.
    """
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "answerable": False,
        "confidence": 0.15,
        "supporting_chunk_indices": [],
        "reason": "Chunks discuss domestic continental shipping and return labels, not German customs duties or VAT."
    })
    mock_client.models.generate_content.return_value = mock_resp

    related_chunks = [
        {
            "chunk_id": 6,
            "document_title": "Shipping and Delivery Guidelines",
            "chunk_index": 1,
            "similarity_score": 0.5835,
            "content": "Standard Ground Shipping: 3 to 5 business days across continental regions."
        }
    ]

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        result = verify_answerability(
            "What are your customs import duty rates and local VAT fees for international shipping to Germany?",
            related_chunks
        )

    assert result.answerable is False
    assert result.requires_human_review is True
    assert result.supporting_chunks == []
    assert "German" in result.reason or "customs" in result.reason


# =====================================================================
# 3. COMPLETELY UNSUPPORTED QUESTIONS (DEMO & GEMINI)
# =====================================================================

def test_answerability_completely_unsupported_question():
    """Verify unsupported out-of-scope questions are flagged for human review."""
    chunks = [
        {
            "chunk_id": 2,
            "document_title": "Customer Return and Refund Policy",
            "chunk_index": 1,
            "similarity_score": 0.52,
            "content": "Refunds are credited back to the original method of payment within 3 to 5 business days."
        }
    ]

    # Test deterministic demo verifier on unsupported Klarna question
    with patch("backend.app.core.config.settings.LLM_PROVIDER", "demo"):
        result = verify_answerability(
            "Can I pay for my order in 4 monthly installments using Klarna or Affirm?",
            chunks
        )

    assert result.answerable is False
    assert result.requires_human_review is True
    assert result.supporting_chunks == []


# =====================================================================
# 4. QUESTIONS REQUIRING MULTIPLE POLICY CHUNKS
# =====================================================================

def test_answerability_multiple_supporting_chunks():
    """Verify that when a question requires multiple policy chunks, all supporting chunks are preserved."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "answerable": True,
        "confidence": 0.91,
        "supporting_chunk_indices": [0, 2],
        "reason": "Chunk 0 states the 30-day window and Chunk 2 explains the complimentary pre-paid return label."
    })
    mock_client.models.generate_content.return_value = mock_resp

    chunks = [
        {"chunk_id": 1, "document_title": "Return Policy", "chunk_index": 0, "similarity_score": 0.72, "content": "30-day return window."},
        {"chunk_id": 5, "document_title": "Shipping Policy", "chunk_index": 0, "similarity_score": 0.45, "content": "24-48 hour processing."},
        {"chunk_id": 3, "document_title": "Return Policy", "chunk_index": 2, "similarity_score": 0.75, "content": "Complimentary pre-paid label for defective items."}
    ]

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        result = verify_answerability(
            "What is the return window and do I get a free shipping label for a defective keyboard?",
            chunks
        )

    assert result.answerable is True
    assert result.requires_human_review is False
    assert len(result.supporting_chunks) == 2
    assert [c["chunk_id"] for c in result.supporting_chunks] == [1, 3]


# =====================================================================
# 5. EMPTY RETRIEVAL RESULTS
# =====================================================================

def test_answerability_empty_retrieval_deterministic_guard():
    """Verify empty retrieval immediately returns answerable=False without calling Gemini."""
    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client") as mock_genai:

        result = verify_answerability("Where is your Chicago retail store?", [])

    mock_genai.assert_not_called()
    assert result.answerable is False
    assert result.confidence == 0.0
    assert result.supporting_chunks == []
    assert result.requires_human_review is True
    assert result.verification_provider == "deterministic_guard"


# =====================================================================
# 6. GEMINI API FAILURES FAIL CLOSED
# =====================================================================

def test_answerability_gemini_api_failure_fails_closed():
    """
    Verify that if Gemini API fails during answerability verification,
    the system fails closed (answerable=False, requires_human_review=True)
    and never leaks sensitive details.
    """
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 ResourceExhausted: secret_key=AIzaSyFake")

    chunks = [
        {"chunk_id": 1, "document_title": "Return Policy", "chunk_index": 0, "similarity_score": 0.65, "content": "30 days."}
    ]

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "AIzaSyFake"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        result = verify_answerability("Can I return this?", chunks)

    assert result.answerable is False
    assert result.confidence == 0.0
    assert result.supporting_chunks == []
    assert result.requires_human_review is True
    assert "AIzaSyFake" not in result.reason
    assert "human review" in result.reason.lower()


# =====================================================================
# 7. DETERMINISTIC PYTHON CONSISTENCY GUARDS
# =====================================================================

def test_answerability_deterministic_consistency_guards():
    """
    Verify Python rules override answerable=True if supporting_chunks is empty
    or confidence is below ANSWERABILITY_CONFIDENCE_THRESHOLD.
    """
    mock_client = MagicMock()
    # Case A: LLM claims answerable=True but returns empty supporting_chunk_indices
    mock_resp_no_chunks = MagicMock()
    mock_resp_no_chunks.text = json.dumps({
        "answerable": True,
        "confidence": 0.85,
        "supporting_chunk_indices": [],
        "reason": "Looks okay."
    })
    # Case B: LLM claims answerable=True but low confidence (0.40 < 0.60)
    mock_resp_low_conf = MagicMock()
    mock_resp_low_conf.text = json.dumps({
        "answerable": True,
        "confidence": 0.40,
        "supporting_chunk_indices": [0],
        "reason": "Uncertain match."
    })
    mock_client.models.generate_content.side_effect = [mock_resp_no_chunks, mock_resp_low_conf]

    chunks = [{"chunk_id": 1, "document_title": "Doc", "chunk_index": 0, "similarity_score": 0.5, "content": "Text"}]

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        res_a = verify_answerability("Question A?", chunks)
        res_b = verify_answerability("Question B?", chunks)

    assert res_a.answerable is False
    assert res_a.requires_human_review is True
    assert "no supporting chunks" in res_a.reason.lower()

    assert res_b.answerable is False
    assert res_b.requires_human_review is True
    assert res_b.supporting_chunks == []
    assert "below minimum threshold" in res_b.reason.lower()


# =====================================================================
# 8. END-TO-END: UNSUPPORTED INFO NEVER REACHES CUSTOMER DRAFT
# =====================================================================

def test_unsupported_question_escalated_and_no_unsupported_claims_in_draft(client: TestClient, db_session: Session):
    """
    End-to-end integration test:
    Submit an unsupported question (German customs VAT) that retrieves semantically related
    shipping chunks above 0.28.
    Verify:
    - Answerability stage rejects the topic-adjacent chunks.
    - Enquiry is marked IN_REVIEW (for human review).
    - Audit log records 'answerability_insufficient_escalated'.
    - Customer-facing draft_body contains safe escalation notice and NO unsupported policy claims.
    - retrieved_sources on the saved draft is empty [].
    """
    create_resp = client.post("/api/v1/enquiries", json={
        "customer_name": "Hans Mueller",
        "customer_email": "hans.mueller@example.de",
        "channel": "email",
        "subject": "German Customs & Import VAT Fees",
        "message": "What are your customs import duty rates and local VAT fees for international shipping to Germany?"
    })
    assert create_resp.status_code == 201
    enquiry_id = create_resp.json()["id"]

    # Simulate search_knowledge_base returning topic-adjacent shipping chunks
    related_chunks = [
        {
            "chunk_id": 6,
            "document_id": 2,
            "document_title": "Shipping and Delivery Guidelines",
            "chunk_index": 1,
            "content": "Standard Ground Shipping: 3 to 5 business days across continental regions via FedEx Ground.",
            "similarity_score": 0.5835
        }
    ]

    with patch("backend.app.api.v1.enquiries.search_knowledge_base", return_value=(related_chunks, True)):
        draft_resp = client.post(f"/api/v1/enquiries/{enquiry_id}/draft")

    assert draft_resp.status_code == 200
    draft_data = draft_resp.json()

    # 1. Verify structured answerability metadata
    ans_details = draft_data["answerability_details"]
    assert ans_details["answerable"] is False
    assert ans_details["requires_human_review"] is True

    # 2. Verify unsupported chunks were stripped from draft sources
    assert draft_data["retrieved_sources"] == []

    # 3. Verify customer-facing draft contains safe escalation and NO shipping policy leakage
    draft_body = draft_data["draft_body"]
    assert "escalated your enquiry to a support specialist for human review" in draft_body
    assert "FedEx Ground" not in draft_body
    assert "3 to 5 business days" not in draft_body

    # 4. Verify enquiry status transitioned to IN_REVIEW
    enq_resp = client.get(f"/api/v1/enquiries/{enquiry_id}")
    assert enq_resp.status_code == 200
    assert enq_resp.json()["status"] == EnquiryStatus.IN_REVIEW.value

    # 5. Verify audit log recorded the escalation
    audit = db_session.query(AuditLog).filter(
        AuditLog.enquiry_id == enquiry_id,
        AuditLog.action == "answerability_insufficient_escalated"
    ).first()
    assert audit is not None
    assert audit.details["answerable"] is False
    assert audit.details["raw_retrieved_count"] == 1
