from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.database import get_db
from backend.app.models.document import Document, DocumentChunk
from backend.app.schemas.document import (
    DocumentResponse, DocumentDetailResponse, SemanticSearchQuery, SearchResultItem
)
from backend.app.services.document_parser import (
    extract_text_from_pdf, extract_text_from_txt, chunk_text
)
from backend.app.services.ai.embeddings import (
    get_embeddings,
    get_active_embedding_config,
    EmbeddingProviderError,
    EmbeddingMismatchError
)
from backend.app.services.ai.rag import search_knowledge_base
from backend.app.services.audit_service import record_audit_log
from backend.app.core.logging import logger

router = APIRouter(prefix="/documents", tags=["Knowledge Base & RAG"])


@router.get("", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    """List all ingested documents in the knowledge base."""
    docs = db.query(Document).order_by(desc(Document.created_at)).all()
    return docs


@router.post("/upload", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF or TXT document, extract text, split into chunks,
    compute embeddings, and store for RAG similarity search.
    Safely rolls back transaction on embedding failure to prevent orphaned records.
    """
    file_bytes = await file.read()
    filename = file.filename or "uploaded_file.txt"
    doc_title = title if title and title.strip() else filename.rsplit(".", 1)[0].replace("_", " ").title()

    file_ext = filename.split(".")[-1].lower() if "." in filename else "txt"
    if file_ext not in ["pdf", "txt", "md", "markdown"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{file_ext}'. Allowed types: .pdf, .txt, .md"
        )

    # 1. Extract text
    if file_ext == "pdf":
        full_text, pages = extract_text_from_pdf(file_bytes)
    else:
        full_text, pages = extract_text_from_txt(file_bytes)

    if not full_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Document appears empty or contains no extractable text."
        )

    active_cfg = get_active_embedding_config()

    try:
        # 2. Create document record
        doc = Document(
            title=doc_title,
            file_name=filename,
            file_type=file_ext,
            file_size_bytes=len(file_bytes),
            chunk_count=0,
            embedding_provider=active_cfg["provider"],
            embedding_model=active_cfg["model"],
            embedding_dimension=active_cfg["dimension"]
        )
        db.add(doc)
        db.flush()

        # 3. Chunk text
        chunks_data = chunk_text(full_text, chunk_size=500, chunk_overlap=100)
        chunk_texts = [c["content"] for c in chunks_data]

        # 4. Generate embeddings (raises EmbeddingProviderError on failure)
        embeddings = get_embeddings(chunk_texts)

        # 5. Save chunks to DB
        chunk_objs = []
        for idx, c in enumerate(chunks_data):
            chunk_obj = DocumentChunk(
                document_id=doc.id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                embedding=embeddings[idx],
                embedding_provider=active_cfg["provider"],
                embedding_model=active_cfg["model"],
                embedding_dimension=active_cfg["dimension"],
                metadata_info=c["metadata_info"]
            )
            db.add(chunk_obj)
            chunk_objs.append(chunk_obj)

        doc.chunk_count = len(chunks_data)
        
        record_audit_log(
            db=db,
            action="document_ingested",
            actor="staff_user",
            details={
                "document_id": doc.id,
                "title": doc.title,
                "chunks_count": doc.chunk_count,
                "file_size": doc.file_size_bytes,
                "embedding_provider": active_cfg["provider"],
                "embedding_model": active_cfg["model"]
            }
        )

        db.commit()
        db.refresh(doc)
        return doc
    except EmbeddingProviderError as e:
        db.rollback()
        logger.error(f"Embedding generation failed during document upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service unavailable. Document processing failed and was rolled back."
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during document ingestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process document embeddings. Upload rolled back."
        )


@router.post("/reindex", response_model=Dict[str, Any])
def reindex_all_documents(db: Session = Depends(get_db)):
    """
    Explicitly re-index all documents in the knowledge base to the active embedding provider and model.
    Processes the entire batch within one atomic database transaction.
    If embedding generation fails for any document, rolls back the entire batch, preserving all existing state.
    """
    docs = db.query(Document).all()
    if not docs:
        return {"status": "success", "reindexed_documents": 0, "reindexed_chunks": 0, "provider": None, "model": None}

    active_cfg = get_active_embedding_config()
    total_chunks = 0
    reindexed_docs = 0

    try:
        for doc in docs:
            chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.chunk_index).all()
            if not chunks:
                continue
            chunk_texts = [c.content for c in chunks]
            new_embeddings = get_embeddings(chunk_texts)
            for idx, chunk in enumerate(chunks):
                chunk.embedding = new_embeddings[idx]
                chunk.embedding_provider = active_cfg["provider"]
                chunk.embedding_model = active_cfg["model"]
                chunk.embedding_dimension = active_cfg["dimension"]
            doc.embedding_provider = active_cfg["provider"]
            doc.embedding_model = active_cfg["model"]
            doc.embedding_dimension = active_cfg["dimension"]
            reindexed_docs += 1
            total_chunks += len(chunks)

        record_audit_log(
            db=db,
            action="all_documents_reindexed",
            actor="staff_user",
            details={
                "reindexed_documents": reindexed_docs,
                "total_chunks": total_chunks,
                "provider": active_cfg["provider"],
                "model": active_cfg["model"]
            }
        )
        db.commit()
    except EmbeddingProviderError as e:
        db.rollback()
        logger.error(f"Embedding re-indexing failed during batch processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider service is unavailable during batch re-indexing. All document updates were rolled back."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error during batch re-indexing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to re-index documents. Entire batch was rolled back."
        )

    return {
        "status": "success",
        "reindexed_documents": reindexed_docs,
        "reindexed_chunks": total_chunks,
        "provider": active_cfg["provider"],
        "model": active_cfg["model"]
    }


@router.post("/search", response_model=List[SearchResultItem])
def search_documents(query_in: SemanticSearchQuery, db: Session = Depends(get_db)):
    """
    Test vector similarity search directly against knowledge base documents.
    Returns the most relevant chunks with cosine similarity score.
    Fails safely if embeddings are mismatched or provider is unavailable.
    """
    try:
        results, _ = search_knowledge_base(db, query_in.query, top_k=query_in.top_k)
    except EmbeddingMismatchError as e:
        logger.error(f"Vector search blocked by embedding mismatch: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except EmbeddingProviderError as e:
        logger.error(f"Vector search failed due to embedding provider error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider service is unavailable."
        )

    return [
        SearchResultItem(
            document_id=r["document_id"],
            document_title=r["document_title"],
            chunk_id=r["chunk_id"],
            chunk_index=r["chunk_index"],
            content=r["content"],
            similarity_score=r["similarity_score"]
        )
        for r in results
    ]


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Retrieve document details and all its chunks."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/{document_id}/reindex", response_model=DocumentDetailResponse)
def reindex_document(document_id: int, db: Session = Depends(get_db)):
    """
    Safely regenerate embeddings for all chunks of a specific document using the active provider and model.
    Keeps existing embeddings intact if re-indexing fails.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index).all()
    if not chunks:
        raise HTTPException(status_code=400, detail="Document has no chunks to reindex")

    active_cfg = get_active_embedding_config()
    chunk_texts = [c.content for c in chunks]

    try:
        new_embeddings = get_embeddings(chunk_texts)
        for idx, chunk in enumerate(chunks):
            chunk.embedding = new_embeddings[idx]
            chunk.embedding_provider = active_cfg["provider"]
            chunk.embedding_model = active_cfg["model"]
            chunk.embedding_dimension = active_cfg["dimension"]

        doc.embedding_provider = active_cfg["provider"]
        doc.embedding_model = active_cfg["model"]
        doc.embedding_dimension = active_cfg["dimension"]

        record_audit_log(
            db=db,
            action="document_reindexed",
            actor="staff_user",
            details={
                "document_id": doc.id,
                "title": doc.title,
                "chunks_count": len(chunks),
                "embedding_provider": active_cfg["provider"],
                "embedding_model": active_cfg["model"]
            }
        )
        db.commit()
        db.refresh(doc)
        return doc
    except EmbeddingProviderError as e:
        db.rollback()
        logger.error(f"Embedding re-indexing failed for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider service is unavailable. Existing document embeddings were preserved."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during re-indexing of document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to re-index document embeddings. Existing embeddings were preserved."
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document and all its chunks from the knowledge base."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    title = doc.title
    db.delete(doc)

    record_audit_log(
        db=db,
        action="document_deleted",
        actor="staff_user",
        details={"document_id": document_id, "title": title}
    )

    db.commit()
    return None
