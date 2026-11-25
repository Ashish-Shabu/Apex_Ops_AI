"""
RAG Evaluation Framework for Apex Ops AI.
Provides repeatable evaluation datasets, retrieval metrics, evaluation runners, and reporting.
"""

from backend.app.evaluation.dataset import (
    EvaluationQuery,
    EvaluationDataset,
    get_default_evaluation_dataset
)
from backend.app.evaluation.metrics import (
    calculate_hit_rate,
    calculate_precision_at_k,
    calculate_recall_at_k,
    calculate_reciprocal_rank,
    calculate_retrieval_metrics
)
from backend.app.evaluation.evaluator import (
    RAGEvaluator,
    EvaluationResult,
    QueryEvaluationDetail
)
from backend.app.evaluation.reporter import (
    generate_text_report,
    generate_markdown_report,
    generate_json_report
)

__all__ = [
    "EvaluationQuery",
    "EvaluationDataset",
    "get_default_evaluation_dataset",
    "calculate_hit_rate",
    "calculate_precision_at_k",
    "calculate_recall_at_k",
    "calculate_reciprocal_rank",
    "calculate_retrieval_metrics",
    "RAGEvaluator",
    "EvaluationResult",
    "QueryEvaluationDetail",
    "generate_text_report",
    "generate_markdown_report",
    "generate_json_report"
]
