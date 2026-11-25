import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from backend.app.evaluation.dataset import (
    EvaluationQuery,
    EvaluationDataset,
    TargetChunkReference,
    get_default_evaluation_dataset
)
from backend.app.evaluation.metrics import (
    calculate_hit_rate,
    calculate_precision_at_k,
    calculate_effective_precision_at_k,
    calculate_recall_at_k,
    calculate_reciprocal_rank,
    calculate_retrieval_metrics
)
from backend.app.evaluation.evaluator import (
    RAGEvaluator,
    EvaluationResult
)
from backend.app.evaluation.reporter import (
    generate_text_report,
    generate_markdown_report,
    generate_json_report
)
from backend.app.evaluation.runner import run_evaluation


# =====================================================================
# 1. METRICS CALCULATION UNIT TESTS AGAINST MANUAL GROUND TRUTH
# =====================================================================

def test_calculate_hit_rate():
    assert calculate_hit_rate([1, 0, 0]) == 1.0
    assert calculate_hit_rate([0, 1, 0]) == 1.0
    assert calculate_hit_rate([0, 0, 0]) == 0.0
    assert calculate_hit_rate([]) == 0.0


def test_calculate_precision_at_k():
    # Standard Precision@K divides by K
    assert calculate_precision_at_k([1, 0, 1], k=3) == round(2 / 3, 4)
    assert calculate_precision_at_k([1, 1, 0], k=2) == 1.0
    assert calculate_precision_at_k([0, 0, 0], k=3) == 0.0
    assert calculate_precision_at_k([1, 1, 1], k=0) == 0.0
    assert calculate_precision_at_k([], k=3) == 0.0


def test_calculate_effective_precision_fewer_than_k():
    """
    When fewer than K chunks are returned, Effective Precision divides by
    the number of actually retrieved chunks rather than penalizing K.
    """
    # Only 1 chunk returned, which is relevant. Under K=3:
    # Standard Precision@3 = 1/3 = 0.3333
    # Effective Precision@3 = 1/1 = 1.0000
    scores = [1]
    assert calculate_precision_at_k(scores, k=3) == round(1 / 3, 4)
    assert calculate_effective_precision_at_k(scores, k=3) == 1.0

    # 2 chunks returned, 1 relevant. Under K=5:
    # Standard Precision@5 = 1/5 = 0.2000
    # Effective Precision@5 = 1/2 = 0.5000
    scores_2 = [1, 0]
    assert calculate_precision_at_k(scores_2, k=5) == 0.2
    assert calculate_effective_precision_at_k(scores_2, k=5) == 0.5

    # Empty retrieved list
    assert calculate_effective_precision_at_k([], k=3) == 0.0


def test_calculate_recall_at_k():
    assert calculate_recall_at_k([1, 0, 0], expected_count=2, k=3) == 0.5
    assert calculate_recall_at_k([1, 1, 0], expected_count=2, k=3) == 1.0
    # Recall is capped at 1.0 if retrieved count exceeds expected
    assert calculate_recall_at_k([1, 1, 1], expected_count=2, k=3) == 1.0
    assert calculate_recall_at_k([0, 0, 0], expected_count=2, k=3) == 0.0
    assert calculate_recall_at_k([1, 0, 0], expected_count=0, k=3) == 0.0


def test_calculate_reciprocal_rank():
    assert calculate_reciprocal_rank([1, 0, 0]) == 1.0
    assert calculate_reciprocal_rank([0, 1, 0]) == 0.5
    assert calculate_reciprocal_rank([0, 0, 1]) == round(1 / 3, 4)
    assert calculate_reciprocal_rank([0, 0, 0]) == 0.0
    # Cutoff K testing
    assert calculate_reciprocal_rank([0, 1, 0], k=1) == 0.0
    assert calculate_reciprocal_rank([0, 1, 0], k=2) == 0.5


def test_manual_ground_truth_metric_calculations():
    """
    Test all metric calculations against hand-calculated, mathematically verified values.
    Query 1: Positive, 1 target. Rel=[1, 0, 0]. Hit@1=1, Hit@3=1, P@1=1, P@3=1/3, R@3=1, RR=1.
    Query 2: Positive, 2 targets. Rel=[0, 1, 0]. Hit@1=0, Hit@3=1, P@1=0, P@3=1/3, R@3=1/2, RR=1/2.
    Query 3: Positive, 1 target. Rel=[0, 0, 0]. Hit@1=0, Hit@3=0, P@1=0, P@3=0, R@3=0, RR=0.
    Query 4: Negative. Rel=[]. Retrieved=0. Correctly rejected.
    """
    query_evals = [
        {"query_id": "q1", "category": "returns", "is_negative": False, "relevance_scores": [1, 0, 0], "expected_relevant_count": 1, "retrieved_count": 3},
        {"query_id": "q2", "category": "shipping", "is_negative": False, "relevance_scores": [0, 1, 0], "expected_relevant_count": 2, "retrieved_count": 3},
        {"query_id": "q3", "category": "returns", "is_negative": False, "relevance_scores": [0, 0, 0], "expected_relevant_count": 1, "retrieved_count": 3},
        {"query_id": "q4", "category": "negative_unsupported", "is_negative": True, "relevance_scores": [], "expected_relevant_count": 0, "retrieved_count": 0}
    ]

    agg = calculate_retrieval_metrics(query_evals, k_values=[1, 3])

    # Total queries: 4. Positive: 3. Negative: 1.
    assert agg.total_queries == 4
    assert agg.positive_queries_count == 3
    assert agg.negative_queries_count == 1

    # Hand-calculated Hit Rate:
    # At K=1: (1 + 0 + 0) / 3 = 1/3 = 0.3333
    assert agg.metrics_by_k[1].hit_rate == round(1 / 3, 4)
    # At K=3: (1 + 1 + 0) / 3 = 2/3 = 0.6667
    assert agg.metrics_by_k[3].hit_rate == round(2 / 3, 4)

    # Hand-calculated Precision@3 (Standard):
    # q1: 1/3, q2: 1/3, q3: 0/3. Mean = (1/3 + 1/3 + 0) / 3 = 2/9 = 0.2222
    assert agg.metrics_by_k[3].precision == round(2 / 9, 4)

    # Hand-calculated Recall@3:
    # q1: 1/1 = 1.0, q2: 1/2 = 0.5, q3: 0/1 = 0.0. Mean = (1.0 + 0.5 + 0.0) / 3 = 1.5 / 3 = 0.5000
    assert agg.metrics_by_k[3].recall == 0.5000

    # Hand-calculated MRR@3:
    # q1: 1.0, q2: 0.5, q3: 0.0. Mean = (1.0 + 0.5 + 0.0) / 3 = 0.5000
    assert agg.metrics_by_k[3].mrr == 0.5000

    # Negative query metrics: 1 true negative out of 1 -> 100%
    assert agg.negative_metrics.total_negative_queries == 1
    assert agg.negative_metrics.correctly_rejected == 1
    assert agg.negative_metrics.false_positives == 0
    assert agg.negative_metrics.correct_rejection_rate == 1.0
    assert agg.negative_metrics.false_positive_rate == 0.0


def test_negative_queries_strictly_excluded_from_positive_metrics():
    """
    Ensure that negative queries (which have 0 expected relevant chunks)
    do not pollute positive retrieval Hit Rate, Precision, Recall, or MRR.
    """
    query_evals = [
        {"query_id": "q1", "category": "returns", "is_negative": False, "relevance_scores": [1, 0, 0], "expected_relevant_count": 1, "retrieved_count": 3},
        {"query_id": "neg1", "category": "negative_unsupported", "is_negative": True, "relevance_scores": [], "expected_relevant_count": 0, "retrieved_count": 0},
        {"query_id": "neg2", "category": "negative_unsupported", "is_negative": True, "relevance_scores": [0], "expected_relevant_count": 0, "retrieved_count": 1}
    ]

    agg = calculate_retrieval_metrics(query_evals, k_values=[1, 3])

    # Only 1 positive query, which had a hit at rank 1
    assert agg.positive_queries_count == 1
    assert agg.negative_queries_count == 2
    # If negative queries were accidentally included in positive denominator, Hit Rate would be 1/3 (0.33)
    # But because they are strictly excluded, Hit Rate is 1/1 = 1.0000
    assert agg.metrics_by_k[1].hit_rate == 1.0
    assert agg.metrics_by_k[3].hit_rate == 1.0
    assert agg.metrics_by_k[3].precision == round(1 / 3, 4)
    assert agg.metrics_by_k[3].recall == 1.0


# =====================================================================
# 2. DATASET VALIDATION TESTS
# =====================================================================

def test_evaluation_dataset_completeness():
    dataset = get_default_evaluation_dataset()
    queries = dataset.queries

    # Must contain at least 20 queries (contains 28)
    assert len(queries) >= 20

    # Verify query ID uniqueness
    query_ids = [q.id for q in queries]
    assert len(query_ids) == len(set(query_ids))

    # Verify required topic coverage
    categories = {q.category for q in queries}
    required_topics = {"refunds", "shipping", "cancellations", "returns", "warranties", "order_policies"}
    assert required_topics.issubset(categories)

    # Verify negative query presence
    negatives = [q for q in queries if q.is_negative]
    assert len(negatives) >= 5
    for n in negatives:
        assert len(n.target_chunks) == 0
        assert n.negative_reasoning is not None and len(n.negative_reasoning) > 10

    # Verify positive queries have explicit target chunk references and ground truth answers
    positives = [q for q in queries if not q.is_negative]
    assert len(positives) >= 20
    for p in positives:
        assert len(p.target_chunks) > 0
        for t in p.target_chunks:
            assert t.document_file.endswith(".txt")
            assert len(t.document_title) > 0
            assert t.chunk_index >= 0
            assert len(t.section_title) > 0
            assert len(t.rationale) > 15
        assert len(p.ground_truth_answer) > 10


# =====================================================================
# 3. GROUND-TRUTH RELEVANCE & ANTI-KEYWORD OVERLAP TESTS
# =====================================================================

def test_keyword_overlap_alone_cannot_mark_chunk_relevant(db_session: Session):
    """
    Ensure that shared keywords (e.g. 'refund', 'return', 'shipping', 'packaging')
    do NOT mark a chunk as relevant if it belongs to a different document or section.
    """
    evaluator = RAGEvaluator(db=db_session)

    # Target is specifically Doc 1 Chunk 0 (Eligibility Window)
    query = EvaluationQuery(
        id="test-kw",
        question="What is the return eligibility window?",
        category="returns",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=0,
                section_title="1. Eligibility Window",
                rationale="Defines the 30 calendar day eligibility window."
            )
        ],
        ground_truth_answer="30 calendar days from delivery."
    )

    # This chunk contains high keyword overlap with 'return', 'refund', 'packaging',
    # but is from 'Shipping and Delivery Guidelines' Chunk 3 (Damaged/Lost shipments)!
    overlap_wrong_doc = {
        "chunk_id": 8,
        "document_title": "Shipping and Delivery Guidelines",
        "chunk_index": 3,
        "content": "If your parcel arrives with visible packaging damage, we will process a return and refund or replacement."
    }

    # Must evaluate to FALSE because it's the wrong document!
    assert evaluator.is_chunk_relevant(overlap_wrong_doc, query) is False


def test_document_title_alone_cannot_mark_wrong_chunk_relevant(db_session: Session):
    """
    Ensure that matching the document title alone is NOT sufficient.
    The chunk_index must match the ground-truth target chunk.
    """
    evaluator = RAGEvaluator(db=db_session)

    query = EvaluationQuery(
        id="test-chunk-idx",
        question="How many days do I have to return an item?",
        category="returns",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=0,
                section_title="1. Eligibility Window",
                rationale="Defines 30 days."
            )
        ],
        ground_truth_answer="30 days."
    )

    # Belongs to Customer Return and Refund Policy, but is Chunk 2 (Pre-paid labels), not Chunk 0!
    wrong_chunk_same_doc = {
        "chunk_id": 3,
        "document_title": "Customer Return and Refund Policy",
        "chunk_index": 2,
        "content": "For voluntary returns, a flat return shipping fee of $7.50 is deducted from the refund total."
    }

    # Must evaluate to FALSE because Chunk 2 does not answer the eligibility window question!
    assert evaluator.is_chunk_relevant(wrong_chunk_same_doc, query) is False

    # Chunk 0 from the same document MUST evaluate to TRUE
    right_chunk = {
        "chunk_id": 1,
        "document_title": "Customer Return and Refund Policy",
        "chunk_index": 0,
        "content": "Customers may request a return within 30 calendar days from the confirmed delivery date."
    }
    assert evaluator.is_chunk_relevant(right_chunk, query) is True


def test_deduplication_of_retrieved_chunks(db_session: Session):
    """
    Verify that if the retrieval system returns duplicate chunks (same chunk_id),
    they are deduplicated before scoring, preventing artificial inflation of metrics.
    """
    query = EvaluationQuery(
        id="test-dedup",
        question="What is the return window?",
        category="returns",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=0,
                section_title="1. Eligibility Window",
                rationale="Defines 30 days."
            )
        ],
        ground_truth_answer="30 days."
    )

    mock_dataset = EvaluationDataset(queries=[query])
    evaluator = RAGEvaluator(db=db_session, dataset=mock_dataset, k_values=[3])

    # Simulate retrieval returning the SAME target chunk twice
    duplicate_results = [
        {"chunk_id": 101, "document_title": "Customer Return and Refund Policy", "chunk_index": 0, "content": "30 days", "similarity_score": 0.8},
        {"chunk_id": 101, "document_title": "Customer Return and Refund Policy", "chunk_index": 0, "content": "30 days", "similarity_score": 0.8},
        {"chunk_id": 102, "document_title": "Customer Return and Refund Policy", "chunk_index": 1, "content": "refund processing", "similarity_score": 0.5}
    ]

    with patch("backend.app.evaluation.evaluator.search_knowledge_base", return_value=(duplicate_results, True)):
        result = evaluator.run()

    detail = result.query_details[0]
    # Deduplication must collapse the duplicate chunk_id 101 into 1 unique chunk
    assert detail.retrieved_count == 2
    # Exactly one relevant score
    assert detail.relevance_scores == [1, 0]


# =====================================================================
# 4. REPORT GENERATION TESTS
# =====================================================================

def test_report_generation_formats(db_session: Session):
    evaluator = RAGEvaluator(db=db_session)
    result = evaluator.run()

    text_rep = generate_text_report(result)
    assert "APEX OPS AI - RAG RETRIEVAL EVALUATION REPORT" in text_rep
    assert "Timestamp (UTC):" in text_rep
    assert "Relevance Threshold:" in text_rep
    assert "NEGATIVE / OUT-OF-SCOPE QUERY ANALYSIS" in text_rep
    assert "Std Prec@K" in text_rep
    assert "Eff Prec@K" in text_rep

    md_rep = generate_markdown_report(result)
    assert "# RAG Retrieval Evaluation Report" in md_rep
    assert "Execution Timestamp (UTC)" in md_rep
    assert "Relevance Threshold" in md_rep
    assert "| Standard Precision@K |" in md_rep

    json_rep = generate_json_report(result)
    assert '"timestamp_utc"' in json_rep
    assert '"relevance_threshold"' in json_rep
    assert '"metrics_by_k"' in json_rep


# =====================================================================
# 5. INTEGRATION RUNNER TEST
# =====================================================================

def test_run_evaluation_runner_integration(db_session: Session):
    """
    Test running the evaluation runner against the test database session.
    Exercises real search_knowledge_base with seeded test documents.
    """
    result = run_evaluation(db=db_session, k_values=[1, 3], output_format="text")
    assert isinstance(result, EvaluationResult)
    assert result.aggregate_metrics.total_queries >= 20
    assert result.aggregate_metrics.positive_queries_count >= 20
    assert result.aggregate_metrics.negative_queries_count >= 5
    assert 1 in result.aggregate_metrics.metrics_by_k
    assert 3 in result.aggregate_metrics.metrics_by_k
    assert 0.0 <= result.aggregate_metrics.metrics_by_k[3].hit_rate <= 1.0
