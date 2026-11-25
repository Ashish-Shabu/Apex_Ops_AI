import io
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from google.genai import types

from backend.app.models.document import Document, DocumentChunk
from backend.app.models.enquiry import Enquiry
from backend.app.services.ai.embeddings import (
    get_embeddings,
    get_embedding,
    EmbeddingProviderError,
    EmbeddingMismatchError,
    get_active_embedding_config
)
from backend.app.services.ai.rag import search_knowledge_base


def test_gemini_embedding_failure_raises_embedding_provider_error():
    """Verify that Gemini embedding API failure raises EmbeddingProviderError and does NOT silently fall back."""
    mock_client = MagicMock()
    mock_client.models.embed_content.side_effect = Exception("ResourceExhausted: 429 Quota exceeded")

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        with pytest.raises(EmbeddingProviderError) as exc_info:
            get_embeddings(["Sample document text to embed"])

        assert "Failed to generate embeddings from Google Gemini API" in str(exc_info.value)
        # Ensure raw API key is not leaked in exception string
        assert "mock_key" not in str(exc_info.value)


def test_document_upload_rollback_on_embedding_failure(client: TestClient, db_session: Session):
    """
    Verify that if embedding generation fails during document upload,
    the transaction is rolled back and no orphaned document or chunk records remain in the database.
    """
    initial_doc_count = db_session.query(Document).count()
    initial_chunk_count = db_session.query(DocumentChunk).count()

    content = "Confidential test document for rollback verification."
    file_tuple = ("rollback_test.txt", io.BytesIO(content.encode("utf-8")), "text/plain")

    with patch("backend.app.api.v1.documents.get_embeddings", side_effect=EmbeddingProviderError("Gemini service unavailable")):
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": file_tuple},
            data={"title": "Rollback Test Document"}
        )

    assert resp.status_code == 503
    assert "Embedding service unavailable" in resp.json()["detail"]

    # Verify database state was completely rolled back
    current_doc_count = db_session.query(Document).count()
    current_chunk_count = db_session.query(DocumentChunk).count()
    assert current_doc_count == initial_doc_count
    assert current_chunk_count == initial_chunk_count

    # Verify no partial document with that title exists
    leaked_doc = db_session.query(Document).filter(Document.title == "Rollback Test Document").first()
    assert leaked_doc is None


def test_vector_search_safe_failure_on_query_embedding_failure(client: TestClient, db_session: Session):
    """Verify vector search and draft generation fail safely (HTTP 503) when query embedding fails."""
    with patch("backend.app.services.ai.rag.get_embedding", side_effect=EmbeddingProviderError("Gemini query embedding failed")):
        # Direct document search endpoint
        resp = client.post("/api/v1/documents/search", json={"query": "return policy timeline", "top_k": 3})
        assert resp.status_code == 503
        assert "Embedding provider service is unavailable" in resp.json()["detail"]

        # Enquiry draft generation endpoint
        enquiry = db_session.query(Enquiry).first()
        assert enquiry is not None
        draft_resp = client.post(f"/api/v1/enquiries/{enquiry.id}/draft")
        assert draft_resp.status_code == 503
        assert "Embedding provider service is unavailable" in draft_resp.json()["detail"]


def test_incompatible_provider_or_model_blocks_search(client: TestClient, db_session: Session):
    """
    Verify that if stored document embeddings were generated with a different provider/model
    than the active embedding provider, vector search fails safely with HTTP 409 Conflict.
    """
    # Test DB is seeded with "demo" provider embeddings
    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"):

        # Attempt search: should be blocked before running any vector math
        resp = client.post("/api/v1/documents/search", json={"query": "test compatibility", "top_k": 3})
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "Embedding compatibility error" in detail
        assert "cannot be compared with active provider" in detail

        # Attempt draft generation: should also return 409
        enquiry = db_session.query(Enquiry).first()
        draft_resp = client.post(f"/api/v1/enquiries/{enquiry.id}/draft")
        assert draft_resp.status_code == 409
        assert "Embedding compatibility error" in draft_resp.json()["detail"]


def test_successful_gemini_embedding_generation_and_storage(client: TestClient, db_session: Session):
    """Verify that valid Gemini embedding generation stores correct provider, model, and dimension metadata."""
    mock_client = MagicMock()
    dummy_vector = [0.12] * 384
    mock_embedding = types.ContentEmbedding(values=dummy_vector)
    mock_resp = types.EmbedContentResponse(embeddings=[mock_embedding])
    mock_client.models.embed_content.return_value = mock_resp

    content = "This is a new Gemini-embedded document for knowledge base testing."
    file_tuple = ("gemini_doc.txt", io.BytesIO(content.encode("utf-8")), "text/plain")

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", "mock_key"), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("backend.app.core.config.settings.EMBEDDING_DIMENSION", 384), \
         patch("google.genai.Client", return_value=mock_client):

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": file_tuple},
            data={"title": "Gemini Ingested Doc"}
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Gemini Ingested Doc"
        assert data["embedding_provider"] == "gemini"
        from backend.app.core.config import settings
        assert data["embedding_model"] == settings.EMBEDDING_MODEL
        assert data["embedding_dimension"] == 384
        assert len(data["chunks"]) > 0
        assert data["chunks"][0]["embedding_provider"] == "gemini"
        assert data["chunks"][0]["embedding_model"] == settings.EMBEDDING_MODEL


def test_document_reindex_and_failure_preservation(client: TestClient, db_session: Session):
    """
    Verify the re-indexing endpoint safely updates embeddings when provider changes,
    and rolls back cleanly preserving existing embeddings if provider fails.
    """
    # 1. Fetch an existing document
    doc = db_session.query(Document).first()
    assert doc is not None
    original_provider = doc.embedding_provider
    first_chunk = doc.chunks[0]
    original_embedding_val = list(first_chunk.embedding)

    # 2. Simulate failure during re-indexing -> existing embeddings must be preserved
    with patch("backend.app.api.v1.documents.get_embeddings", side_effect=EmbeddingProviderError("Reindex quota limit reached")):
        fail_resp = client.post(f"/api/v1/documents/{doc.id}/reindex")
        assert fail_resp.status_code == 503
        assert "Existing document embeddings were preserved" in fail_resp.json()["detail"]

    # Verify DB chunks and doc are untouched
    db_session.refresh(doc)
    db_session.refresh(first_chunk)
    assert doc.embedding_provider == original_provider
    assert list(first_chunk.embedding) == original_embedding_val

    # 3. Successful single document re-indexing
    success_resp = client.post(f"/api/v1/documents/{doc.id}/reindex")
    assert success_resp.status_code == 200
    reindexed_data = success_resp.json()
    assert reindexed_data["id"] == doc.id
    assert reindexed_data["embedding_provider"] == "demo"

    # 4. Successful bulk re-indexing
    bulk_resp = client.post("/api/v1/documents/reindex")
    assert bulk_resp.status_code == 200
    bulk_data = bulk_resp.json()
    assert bulk_data["status"] == "success"
    assert bulk_data["reindexed_documents"] > 0


def test_bulk_reindex_batch_rollback_on_partial_failure(client: TestClient, db_session: Session):
    """
    Verify that if embedding generation fails midway through bulk re-indexing (e.g., doc 2 of 3),
    the entire transaction is rolled back so that even doc 1's original embeddings and metadata
    are preserved without leaving partially migrated records in the database.
    """
    docs = db_session.query(Document).order_by(Document.id).all()
    assert len(docs) >= 3
    doc1, doc2, doc3 = docs[0], docs[1], docs[2]

    # Snapshot initial state for all 3 documents and their chunks
    original_states = {}
    for d in [doc1, doc2, doc3]:
        original_states[d.id] = {
            "provider": d.embedding_provider,
            "model": d.embedding_model,
            "dimension": d.embedding_dimension,
            "chunk_embeddings": [list(c.embedding) for c in d.chunks]
        }

    # Simulate get_embeddings: succeeds on doc 1, fails on doc 2
    call_count = 0
    def mock_get_embeddings(chunk_texts):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First doc succeeds with dummy values
            return [[0.888] * len(chunk_texts[0])] * len(chunk_texts)
        # Second doc fails with provider error
        raise EmbeddingProviderError("Gemini quota exhausted on doc 2")

    with patch("backend.app.api.v1.documents.get_embeddings", side_effect=mock_get_embeddings):
        resp = client.post("/api/v1/documents/reindex")

    assert resp.status_code == 503
    assert "Embedding provider service is unavailable during batch re-indexing" in resp.json()["detail"]

    # Refresh DB session and verify all 3 documents and their chunks preserved original state
    for d in [doc1, doc2, doc3]:
        db_session.refresh(d)
        assert d.embedding_provider == original_states[d.id]["provider"]
        assert d.embedding_model == original_states[d.id]["model"]
        assert d.embedding_dimension == original_states[d.id]["dimension"]
        for idx, c in enumerate(d.chunks):
            db_session.refresh(c)
            assert list(c.embedding) == original_states[d.id]["chunk_embeddings"][idx]


def test_embedding_dimension_mismatch_blocks_search(client: TestClient, db_session: Session):
    """
    Verify that if stored document chunks have an embedding dimension different from the active
    configuration, search_knowledge_base detects the mismatch, returns HTTP 409, and vector search
    is never executed.
    """
    first_chunk = db_session.query(DocumentChunk).filter(DocumentChunk.embedding.isnot(None)).first()
    assert first_chunk is not None
    original_dim = first_chunk.embedding_dimension

    try:
        first_chunk.embedding_dimension = 9999
        db_session.commit()

        # Patch vector search implementations to verify they are never reached
        with patch("backend.app.services.ai.rag._search_fallback") as mock_fallback, \
             patch("backend.app.services.ai.rag._search_pgvector") as mock_pgvector:

            resp = client.post("/api/v1/documents/search", json={"query": "return policy inquiry", "top_k": 3})
            assert resp.status_code == 409
            detail = resp.json()["detail"]
            assert "Embedding compatibility error" in detail
            assert "stored dimension 9999 != active dimension" in detail

            # Vector search functions must never be executed
            mock_fallback.assert_not_called()
            mock_pgvector.assert_not_called()
    finally:
        first_chunk.embedding_dimension = original_dim
        db_session.commit()


def test_safe_logging_does_not_leak_api_keys(caplog):
    """
    Verify that raw provider exception messages containing API keys or query URLs are never logged
    or exposed in API error responses.
    """
    import logging
    fake_secret_key = "AIzaSyFakeSecretKey123456789ABCDEF"
    fake_exception_msg = f"Failed to connect to https://generativelanguage.googleapis.com/v1beta/models?key={fake_secret_key}"

    mock_client = MagicMock()
    mock_client.models.embed_content.side_effect = Exception(fake_exception_msg)

    with patch("backend.app.core.config.settings.GEMINI_API_KEY", fake_secret_key), \
         patch("backend.app.core.config.settings.LLM_PROVIDER", "gemini"), \
         patch("google.genai.Client", return_value=mock_client):

        with caplog.at_level(logging.DEBUG):
            with pytest.raises(EmbeddingProviderError) as exc_info:
                get_embeddings(["Confidential knowledge query"])

        # 1. Secret key must not appear in the raised exception message
        assert fake_secret_key not in str(exc_info.value)
        # 2. Secret key must not appear anywhere in captured log output
        assert fake_secret_key not in caplog.text
        # 3. Safe sanitized log entry must be present
        assert "Google Gemini embedding API call failed with exception type" in caplog.text

