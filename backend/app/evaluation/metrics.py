from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class RetrievalMetricsAtK(BaseModel):
    """Retrieval metrics computed at a specific cutoff K."""
    k: int
    hit_rate: float = Field(..., description="Proportion of positive queries with at least one ground-truth relevant chunk in top-K")
    precision: float = Field(..., description="Standard Precision@K: (relevant chunks in top-K) / K")
    effective_precision: float = Field(..., description="Precision over retrieved: (relevant chunks in top-K) / min(K, total_retrieved)")
    recall: float = Field(..., description="Recall@K: (relevant chunks in top-K) / (total ground-truth expected chunks)")
    mrr: float = Field(..., description="Mean Reciprocal Rank (MRR@K) of the first relevant retrieved chunk")


class NegativeQueryMetrics(BaseModel):
    """Metrics for queries where no relevant knowledge base answer exists."""
    total_negative_queries: int
    correctly_rejected: int = Field(..., description="True Negatives: 0 chunks returned above relevance threshold")
    false_positives: int = Field(..., description="False Alarms: 1 or more chunks returned above relevance threshold")
    correct_rejection_rate: float = Field(..., description="Specificity: correctly_rejected / total_negative_queries")
    false_positive_rate: float = Field(..., description="1 - correct_rejection_rate")


class AggregateRetrievalMetrics(BaseModel):
    """Complete summary of retrieval metrics across all evaluated queries."""
    total_queries: int
    positive_queries_count: int
    negative_queries_count: int
    metrics_by_k: Dict[int, RetrievalMetricsAtK]
    negative_metrics: Optional[NegativeQueryMetrics] = None
    category_metrics: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


def calculate_hit_rate(relevance_scores: List[int]) -> float:
    """
    Returns 1.0 if at least one item in relevance_scores is relevant (1), else 0.0.
    relevance_scores: binary list e.g. [0, 1, 0]
    """
    return 1.0 if any(r > 0 for r in relevance_scores) else 0.0


def calculate_precision_at_k(relevance_scores: List[int], k: int) -> float:
    """
    Standard Information Retrieval Precision@K = (number of relevant items in top-K) / K.
    Penalizes retrieval systems when fewer than K chunks are returned.
    """
    if k <= 0:
        return 0.0
    top_k = relevance_scores[:k]
    relevant_count = sum(1 for r in top_k if r > 0)
    return round(relevant_count / k, 4)


def calculate_effective_precision_at_k(relevance_scores: List[int], k: int) -> float:
    """
    Effective Precision@K = (number of relevant items in top-K) / min(K, len(relevance_scores)).
    Evaluates precision exclusively over the chunks actually returned up to rank K.
    Avoids penalizing systems when the total retrieved count is naturally fewer than K.
    """
    if k <= 0:
        return 0.0
    top_k = relevance_scores[:k]
    if not top_k:
        return 0.0
    relevant_count = sum(1 for r in top_k if r > 0)
    return round(relevant_count / len(top_k), 4)


def calculate_recall_at_k(relevance_scores: List[int], expected_count: int, k: int) -> float:
    """
    Recall@K = (number of unique relevant items in top-K) / expected_count.
    Capped at 1.0.
    """
    if expected_count <= 0 or k <= 0:
        return 0.0
    top_k = relevance_scores[:k]
    relevant_count = sum(1 for r in top_k if r > 0)
    return round(min(1.0, relevant_count / expected_count), 4)


def calculate_reciprocal_rank(relevance_scores: List[int], k: Optional[int] = None) -> float:
    """
    Reciprocal Rank = 1 / rank of first relevant item (1-indexed).
    Returns 0.0 if no relevant item is found in top-K.
    """
    scores = relevance_scores[:k] if k is not None else relevance_scores
    for rank, score in enumerate(scores, start=1):
        if score > 0:
            return round(1.0 / rank, 4)
    return 0.0


def calculate_retrieval_metrics(
    query_evaluations: List[Dict[str, Any]],
    k_values: List[int] = [1, 3, 5]
) -> AggregateRetrievalMetrics:
    """
    Computes aggregate metrics across all evaluated queries.
    Strictly separates positive queries from negative queries.
    """
    positive_evals = [q for q in query_evaluations if not q.get("is_negative", False)]
    negative_evals = [q for q in query_evaluations if q.get("is_negative", False)]

    metrics_by_k: Dict[int, RetrievalMetricsAtK] = {}

    for k in sorted(k_values):
        if not positive_evals:
            metrics_by_k[k] = RetrievalMetricsAtK(
                k=k, hit_rate=0.0, precision=0.0, effective_precision=0.0, recall=0.0, mrr=0.0
            )
            continue

        hits = []
        precisions = []
        effective_precisions = []
        recalls = []
        reciprocal_ranks = []

        for q in positive_evals:
            rel = q.get("relevance_scores", [])
            expected_count = max(1, q.get("expected_relevant_count", 1))

            hits.append(calculate_hit_rate(rel[:k]))
            precisions.append(calculate_precision_at_k(rel, k))
            effective_precisions.append(calculate_effective_precision_at_k(rel, k))
            recalls.append(calculate_recall_at_k(rel, expected_count, k))
            reciprocal_ranks.append(calculate_reciprocal_rank(rel, k))

        metrics_by_k[k] = RetrievalMetricsAtK(
            k=k,
            hit_rate=round(sum(hits) / len(hits), 4),
            precision=round(sum(precisions) / len(precisions), 4),
            effective_precision=round(sum(effective_precisions) / len(effective_precisions), 4),
            recall=round(sum(recalls) / len(recalls), 4),
            mrr=round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4)
        )

    # Negative query metrics
    neg_metrics = None
    if negative_evals:
        total_neg = len(negative_evals)
        correctly_rejected = sum(1 for q in negative_evals if q.get("retrieved_count", 0) == 0)
        false_positives = total_neg - correctly_rejected
        crr = round(correctly_rejected / total_neg, 4) if total_neg > 0 else 1.0
        neg_metrics = NegativeQueryMetrics(
            total_negative_queries=total_neg,
            correctly_rejected=correctly_rejected,
            false_positives=false_positives,
            correct_rejection_rate=crr,
            false_positive_rate=round(1.0 - crr, 4)
        )

    # Category breakdown (computed at primary k, e.g. k=3 or first k)
    primary_k = 3 if 3 in k_values else (k_values[0] if k_values else 3)
    categories = sorted(list({q.get("category", "general") for q in query_evaluations}))
    category_metrics: Dict[str, Dict[str, Any]] = {}

    for cat in categories:
        cat_evals = [q for q in query_evaluations if q.get("category") == cat]
        cat_pos = [q for q in cat_evals if not q.get("is_negative", False)]
        cat_neg = [q for q in cat_evals if q.get("is_negative", False)]

        cat_summary: Dict[str, Any] = {
            "total_queries": len(cat_evals),
            "positive_queries": len(cat_pos),
            "negative_queries": len(cat_neg)
        }

        if cat_pos:
            c_hits = [calculate_hit_rate(q.get("relevance_scores", [])[:primary_k]) for q in cat_pos]
            c_precs = [calculate_precision_at_k(q.get("relevance_scores", []), primary_k) for q in cat_pos]
            c_eff_precs = [calculate_effective_precision_at_k(q.get("relevance_scores", []), primary_k) for q in cat_pos]
            c_recalls = [calculate_recall_at_k(q.get("relevance_scores", []), max(1, q.get("expected_relevant_count", 1)), primary_k) for q in cat_pos]
            c_mrrs = [calculate_reciprocal_rank(q.get("relevance_scores", []), primary_k) for q in cat_pos]

            cat_summary[f"hit_rate@{primary_k}"] = round(sum(c_hits) / len(c_hits), 4)
            cat_summary[f"precision@{primary_k}"] = round(sum(c_precs) / len(c_precs), 4)
            cat_summary[f"effective_precision@{primary_k}"] = round(sum(c_eff_precs) / len(c_eff_precs), 4)
            cat_summary[f"recall@{primary_k}"] = round(sum(c_recalls) / len(c_recalls), 4)
            cat_summary[f"mrr@{primary_k}"] = round(sum(c_mrrs) / len(c_mrrs), 4)

        if cat_neg:
            c_corr = sum(1 for q in cat_neg if q.get("retrieved_count", 0) == 0)
            cat_summary["correct_rejection_rate"] = round(c_corr / len(cat_neg), 4)
            cat_summary["false_positive_rate"] = round((len(cat_neg) - c_corr) / len(cat_neg), 4)

        category_metrics[cat] = cat_summary

    return AggregateRetrievalMetrics(
        total_queries=len(query_evaluations),
        positive_queries_count=len(positive_evals),
        negative_queries_count=len(negative_evals),
        metrics_by_k=metrics_by_k,
        negative_metrics=neg_metrics,
        category_metrics=category_metrics
    )
