from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DocumentChunkResponse(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    metadata_info: Dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: int
    title: str
    file_name: str
    file_type: str
    file_size_bytes: int
    chunk_count: int
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    chunks: List[DocumentChunkResponse] = []

    model_config = ConfigDict(from_attributes=True)


class SemanticSearchQuery(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=4, ge=1, le=20)


class SearchResultItem(BaseModel):
    document_id: int
    document_title: str
    chunk_id: int
    chunk_index: int
    content: str
    similarity_score: float
