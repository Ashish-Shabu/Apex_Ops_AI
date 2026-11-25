from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.models.document import Document, DocumentChunk
from backend.app.services.ai.embeddings import (
    get_embedding,
    cosine_similarity,
    get_active_embedding_config,
    EmbeddingMismatchError,
    EmbeddingProviderError
)

RELEVANCE_THRESHOLD = 0.28  # Minimum cosine similarity to be considered relevant


def search_knowledge_base(
    db: Session,
    query: str,
    top_k: int = 4
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Search document chunks for query after ensuring provider and model compatibility.
    Raises EmbeddingMismatchError if stored chunk embeddings do not match active provider/model.
    Raises EmbeddingProviderError if query embedding generation fails.
    Returns:
        (retrieved_chunks, has_sufficient_knowledge)
    """
    if not query.strip():
        return [], False

    # 1. Check if any embedded document chunks exist
    chunk_count = db.query(DocumentChunk).filter(DocumentChunk.embedding.isnot(None)).count()
    if chunk_count == 0:
        return [], False

    # 2. Compatibility validation: Never compare vectors from mismatched providers, models, or dimensions
    active_cfg = get_active_embedding_config()
    stored_configs = db.query(
        DocumentChunk.embedding_provider,
        DocumentChunk.embedding_model,
        DocumentChunk.embedding_dimension
    ).filter(DocumentChunk.embedding.isnot(None)).distinct().all()

    mismatches = []
    for prov, model, dim in stored_configs:
        if prov is None:
            mismatches.append("chunks with missing embedding provider metadata (re-indexing required)")
        elif prov != active_cfg["provider"]:
            mismatches.append(f"stored provider '{prov}' != active provider '{active_cfg['provider']}'")
        elif prov != "demo" and model != active_cfg["model"]:
            mismatches.append(f"stored model '{model}' != active model '{active_cfg['model']}'")
        elif dim is None:
            mismatches.append("chunks with missing embedding dimension metadata (re-indexing required)")
        elif dim != active_cfg["dimension"]:
            mismatches.append(f"stored dimension {dim} != active dimension {active_cfg['dimension']}")

    if mismatches:
        mismatch_desc = "; ".join(mismatches)
        err_msg = (
            f"Embedding compatibility error: Knowledge base chunks use [{mismatch_desc}], "
            f"which cannot be compared with active provider '{active_cfg['provider']}' ({active_cfg['model']}, dim={active_cfg['dimension']}). "
            f"Please re-index documents to match the active embedding model."
        )
        logger.error(err_msg)
        raise EmbeddingMismatchError(err_msg)

    # 3. Generate query vector (raises EmbeddingProviderError on provider failure)
    query_embedding = get_embedding(query)
    
    # 4. If using PostgreSQL with pgvector
    if settings.DATABASE_URL.startswith("postgresql"):
        try:
            return _search_pgvector(db, query_embedding, top_k)
        except Exception as e:
            logger.warning(f"pgvector query failed: {e}. Falling back to in-memory cosine similarity.")

    # 5. In-memory / SQLite vector similarity search
    return _search_fallback(db, query_embedding, top_k)


def _search_pgvector(
    db: Session,
    query_vector: List[float],
    top_k: int
) -> Tuple[List[Dict[str, Any]], bool]:
    """Execute pgvector cosine distance search in PostgreSQL."""
    sql = text("""
        SELECT 
            dc.id AS chunk_id,
            dc.document_id,
            dc.chunk_index,
            dc.content,
            d.title AS document_title,
            1 - (dc.embedding <=> :query_vector::vector) AS similarity
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        ORDER BY similarity DESC
        LIMIT :top_k
    """)
    result = db.execute(sql, {"query_vector": str(query_vector), "top_k": top_k}).fetchall()

    chunks = []
    for row in result:
        sim = float(row.similarity)
        if sim >= RELEVANCE_THRESHOLD:
            chunks.append({
                "chunk_id": row.chunk_id,
                "document_id": row.document_id,
                "document_title": row.document_title,
                "chunk_index": row.chunk_index,
                "content": row.content,
                "similarity_score": round(sim, 4)
            })

    has_sufficient = len(chunks) > 0
    return chunks, has_sufficient


def _search_fallback(
    db: Session,
    query_vector: List[float],
    top_k: int
) -> Tuple[List[Dict[str, Any]], bool]:
    """In-memory cosine similarity search across all stored document chunks."""
    all_chunks = db.query(DocumentChunk, Document.title).join(
        Document, Document.id == DocumentChunk.document_id
    ).all()

    scored_chunks = []
    for chunk, doc_title in all_chunks:
        if not chunk.embedding:
            continue
        sim = cosine_similarity(query_vector, chunk.embedding)
        scored_chunks.append({
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "document_title": doc_title,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "similarity_score": round(sim, 4)
        })

    # Sort descending by similarity
    scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
    top_results = [c for c in scored_chunks[:top_k] if c["similarity_score"] >= RELEVANCE_THRESHOLD]
    
    has_sufficient = len(top_results) > 0 and (top_results[0]["similarity_score"] >= RELEVANCE_THRESHOLD)
    return top_results, has_sufficient
