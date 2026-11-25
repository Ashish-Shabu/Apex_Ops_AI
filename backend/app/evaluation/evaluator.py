from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.services.ai.rag import search_knowledge_base, RELEVANCE_THRESHOLD
from backend.app.services.ai.embeddings import (
    get_active_embedding_config,
    EmbeddingError
)
from backend.app.evaluation.dataset import (
    EvaluationQuery,
    EvaluationDataset,
    TargetChunkReference,
    get_default_evaluation_dataset
)
from backend.app.evaluation.metrics import (
    calculate_retrieval_metrics,
    calculate_reciprocal_rank,
    AggregateRetrievalMetrics
)
from backend.app.core.logging import logger


class QueryEvaluationDetail(BaseModel):
    """Detailed evaluation result for an individual test question."""
    query_id: str
    question: str
    category: str
    is_negative: bool
    ground_truth_answer: str
    target_chunks: List[TargetChunkReference] = Field(default_factory=list)
    retrieved_count: int
    top_similarity_score: Optional[float] = None
    retrieved_chunks_summary: List[Dict[str, Any]] = Field(default_factory=list)
    relevance_scores: List[int] = Field(default_factory=list)
    is_hit_by_k: Dict[int, bool] = Field(default_factory=dict)
    first_hit_rank: Optional[int] = None
    reciprocal_rank: float = 0.0
    correctly_rejected: Optional[bool] = None
    negative_reasoning: Optional[str] = None
    notes: Optional[str] = None


class EvaluationResult(BaseModel):
    """Overall outcome of a RAG evaluation run."""
    dataset_name: str
    dataset_version: str
    timestamp_utc: str
    provider: str
    model: str
    dimension: int
    database_backend: str = "sqlite"
    relevance_threshold: float
    is_mock_or_demo: bool
    k_values: List[int]
    aggregate_metrics: AggregateRetrievalMetrics
    query_details: List[QueryEvaluationDetail]


class RAGEvaluator:
    """
    Repeatable evaluation runner for the knowledge base retrieval pipeline.
    Executes questions against search_knowledge_base() and evaluates retrieved chunks
    against ground-truth annotations without modifying the production retrieval pipeline.
    """

    def __init__(
        self,
        db: Session,
        dataset: Optional[EvaluationDataset] = None,
        k_values: List[int] = [1, 3, 5]
    ):
        self.db = db
        self.dataset = dataset or get_default_evaluation_dataset()
        self.k_values = sorted(k_values)
        self.max_k = max(self.k_values) if self.k_values else 5

    def is_chunk_relevant(self, chunk: Dict[str, Any], query: EvaluationQuery) -> bool:
        """
        Determines whether a retrieved chunk is a verified ground-truth answer chunk.
        
        Strict rules:
        1. Negative queries NEVER match any chunk (returns False).
        2. Positive queries MUST match an explicit TargetChunkReference by:
           - Document title or file name
           - AND exact chunk_index.
        3. Keyword overlap alone or document title match alone DOES NOT qualify as relevant.
        """
        if query.is_negative:
            return False

        if not query.target_chunks:
            return False

        chunk_doc_title = str(chunk.get("document_title", "")).strip().lower()
        chunk_idx = chunk.get("chunk_index")

        for target in query.target_chunks:
            target_title = target.document_title.strip().lower()
            target_file = target.document_file.strip().lower()

            doc_matches = (
                chunk_doc_title == target_title or
                target_title in chunk_doc_title or
                chunk_doc_title in target_title
            )

            if doc_matches and chunk_idx == target.chunk_index:
                return True

        return False

    def evaluate_query(self, query: EvaluationQuery) -> QueryEvaluationDetail:
        """
        Runs a single query through search_knowledge_base(), deduplicates chunks,
        and computes strict relevance metrics.
        """
        raw_retrieved_chunks = []
        has_sufficient = False
        error_note = None

        try:
            raw_retrieved_chunks, has_sufficient = search_knowledge_base(
                self.db,
                query.question,
                top_k=self.max_k
            )
        except EmbeddingError as ee:
            error_note = f"Embedding error during search: {ee}"
            logger.warning(f"Evaluator query '{query.id}' encountered embedding error: {ee}")
        except Exception as ex:
            error_note = f"Unexpected retrieval error: {ex}"
            logger.error(f"Evaluator query '{query.id}' failed unexpectedly: {ex}")

        # Deduplicate retrieved chunks by chunk_id or (document_id, chunk_index)
        # to ensure duplicate results do not artificially inflate precision or recall
        seen_keys = set()
        deduped_chunks = []
        for c in raw_retrieved_chunks:
            cid = c.get("chunk_id")
            key = cid if cid is not None else (c.get("document_id"), c.get("chunk_index"))
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_chunks.append(c)

        # Assess strict ground-truth relevance for each retrieved chunk
        relevance_scores: List[int] = []
        retrieved_summary = []

        for c in deduped_chunks:
            is_rel = 1 if self.is_chunk_relevant(c, query) else 0
            relevance_scores.append(is_rel)
            retrieved_summary.append({
                "chunk_id": c.get("chunk_id"),
                "document_title": c.get("document_title"),
                "chunk_index": c.get("chunk_index"),
                "similarity_score": c.get("similarity_score"),
                "is_relevant": bool(is_rel)
            })

        # Calculate hits at each cutoff K
        is_hit_by_k: Dict[int, bool] = {}
        for k in self.k_values:
            is_hit_by_k[k] = any(r > 0 for r in relevance_scores[:k])

        # Reciprocal rank & first hit rank
        first_hit_rank = None
        for rank, score in enumerate(relevance_scores, start=1):
            if score > 0:
                first_hit_rank = rank
                break

        rr = calculate_reciprocal_rank(relevance_scores, k=self.max_k)

        # Negative query evaluation
        # Correctly rejected (True Negative) if 0 chunks retrieved above threshold.
        # If chunks returned, it is a False Positive (hallucination / irrelevant context risk).
        correctly_rejected = None
        if query.is_negative:
            correctly_rejected = (len(deduped_chunks) == 0)

        top_score = deduped_chunks[0].get("similarity_score") if deduped_chunks else None

        return QueryEvaluationDetail(
            query_id=query.id,
            question=query.question,
            category=query.category,
            is_negative=query.is_negative,
            ground_truth_answer=query.ground_truth_answer,
            target_chunks=query.target_chunks,
            retrieved_count=len(deduped_chunks),
            top_similarity_score=top_score,
            retrieved_chunks_summary=retrieved_summary,
            relevance_scores=relevance_scores,
            is_hit_by_k=is_hit_by_k,
            first_hit_rank=first_hit_rank,
            reciprocal_rank=rr,
            correctly_rejected=correctly_rejected,
            negative_reasoning=query.negative_reasoning,
            notes=error_note
        )

    def run(self) -> EvaluationResult:
        """
        Executes evaluation for all queries in the dataset and returns an EvaluationResult.
        """
        active_cfg = get_active_embedding_config()
        is_mock_or_demo = (active_cfg["provider"] == "demo")
        now_utc = datetime.now(timezone.utc).isoformat()

        details: List[QueryEvaluationDetail] = []
        eval_items_for_metrics: List[Dict[str, Any]] = []

        for q in self.dataset.queries:
            detail = self.evaluate_query(q)
            details.append(detail)

            expected_count = len(q.target_chunks) if q.target_chunks else 1

            eval_items_for_metrics.append({
                "query_id": q.id,
                "category": q.category,
                "is_negative": q.is_negative,
                "relevance_scores": detail.relevance_scores,
                "expected_relevant_count": expected_count,
                "retrieved_count": detail.retrieved_count
            })

        aggregate = calculate_retrieval_metrics(
            eval_items_for_metrics,
            k_values=self.k_values
        )

        from backend.app.core.config import settings
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql"):
            db_backend = "PostgreSQL + pgvector"
        elif db_url.startswith("sqlite"):
            db_backend = f"SQLite (local fallback: {db_url})"
        else:
            db_backend = db_url

        return EvaluationResult(
            dataset_name=self.dataset.name,
            dataset_version=self.dataset.version,
            timestamp_utc=now_utc,
            provider=active_cfg["provider"],
            model=active_cfg["model"],
            dimension=active_cfg["dimension"],
            database_backend=db_backend,
            relevance_threshold=float(RELEVANCE_THRESHOLD),
            is_mock_or_demo=is_mock_or_demo,
            k_values=self.k_values,
            aggregate_metrics=aggregate,
            query_details=details
        )
