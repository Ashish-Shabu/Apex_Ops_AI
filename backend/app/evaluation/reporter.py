import json
from typing import Dict, Any
from backend.app.evaluation.evaluator import EvaluationResult


def generate_text_report(result: EvaluationResult) -> str:
    """
    Renders a human-readable ASCII text report summarizing evaluation results.
    Explicitly reports active provider, model, dimension, relevance threshold, and timestamp.
    """
    lines = []
    sep = "=" * 88
    subsep = "-" * 88

    lines.append(sep)
    lines.append("                  APEX OPS AI - RAG RETRIEVAL EVALUATION REPORT")
    lines.append(sep)
    lines.append(f"Timestamp (UTC):    {result.timestamp_utc}")
    lines.append(f"Dataset:            {result.dataset_name} (v{result.dataset_version})")

    # Prominent provider & execution mode disclosure
    if result.is_mock_or_demo:
        provider_badge = f"[DEMO / MOCK MODE] Deterministic Offline Embeddings ({result.dimension}d)"
    else:
        provider_badge = f"[LIVE PRODUCTION PROVIDER] {result.provider.upper()} ({result.model}, {result.dimension}d)"

    lines.append(f"Execution Mode:     {provider_badge}")
    lines.append(f"Database Backend:   {result.database_backend}")
    lines.append(f"Relevance Threshold:{result.relevance_threshold:.2f} (Minimum cosine similarity to retrieve)")
    lines.append(f"Total Questions:    {result.aggregate_metrics.total_queries} "
                 f"({result.aggregate_metrics.positive_queries_count} Positive, "
                 f"{result.aggregate_metrics.negative_queries_count} Negative/Unsupported)")
    lines.append(subsep)

    # 1. Overall Metrics Table by K
    lines.append("1. RETRIEVAL PERFORMANCE BY CUTOFF (K)")
    lines.append(f"{'K':<6} | {'Hit Rate@K':<12} | {'Std Prec@K':<12} | {'Eff Prec@K':<12} | {'Recall@K':<12} | {'MRR@K':<10}")
    lines.append("-" * 6 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 10)

    for k, m in sorted(result.aggregate_metrics.metrics_by_k.items()):
        lines.append(
            f"{k:<6} | {m.hit_rate * 100:>10.1f}% | {m.precision * 100:>10.1f}% | "
            f"{m.effective_precision * 100:>10.1f}% | {m.recall * 100:>10.1f}% | {m.mrr:>10.4f}"
        )
    lines.append("")
    lines.append("Note: 'Std Prec@K' penalizes systems when < K chunks are returned (relevant / K).")
    lines.append("      'Eff Prec@K' measures precision over retrieved chunks (relevant / min(K, total_retrieved)).")
    lines.append("")

    # 2. Negative Query Rejection Performance
    lines.append("2. NEGATIVE / OUT-OF-SCOPE QUERY ANALYSIS")
    neg = result.aggregate_metrics.negative_metrics
    if neg:
        lines.append(f"Total Negative Queries:      {neg.total_negative_queries}")
        lines.append(f"Correctly Rejected (TN):     {neg.correctly_rejected} ({neg.correct_rejection_rate * 100:.1f}%)")
        lines.append(f"False Positives (FP):        {neg.false_positives} ({neg.false_positive_rate * 100:.1f}%)")
        rejection_status = "EXCELLENT" if neg.correct_rejection_rate >= 0.8 else ("ACCEPTABLE" if neg.correct_rejection_rate >= 0.6 else "NEEDS_TUNING")
        lines.append(f"Rejection Assessment:        {rejection_status}")
        lines.append("")
        lines.append("Negative Query Audit Details:")
        lines.append(f"{'ID':<8} | {'Status':<14} | {'Retr#':<5} | {'Top Sim':<8} | Question & Policy Boundary Reason")
        lines.append("-" * 8 + "-+-" + "-" * 14 + "-+-" + "-" * 5 + "-+-" + "-" * 8 + "-+-" + "-" * 45)
        for q in result.query_details:
            if not q.is_negative:
                continue
            status = "TRUE_NEGATIVE" if q.correctly_rejected else "FALSE_POSITIVE"
            top_sim = f"{q.top_similarity_score:.3f}" if q.top_similarity_score is not None else "0.000"
            lines.append(f"{q.query_id:<8} | {status:<14} | {q.retrieved_count:<5} | {top_sim:<8} | {q.question}")
            if q.negative_reasoning:
                lines.append(f"{'':<8} | {'':<14} | {'':<5} | {'':<8} | -> Why out-of-scope: {q.negative_reasoning[:75]}...")
    else:
        lines.append("No negative queries evaluated.")
    lines.append("")

    # 3. Category Breakdown Table
    lines.append("3. PERFORMANCE BY CATEGORY")
    primary_k = 3 if 3 in result.k_values else (result.k_values[0] if result.k_values else 3)
    lines.append(f"{'Category':<22} | {'Total':<6} | {'Hit@' + str(primary_k):<8} | {'Prec@' + str(primary_k):<8} | {'Rec@' + str(primary_k):<8} | {'MRR@' + str(primary_k):<8} | {'Rejection':<10}")
    lines.append("-" * 22 + "-+-" + "-" * 6 + "-+-" + "-" * 8 + "-+-" + "-" * 8 + "-+-" + "-" * 8 + "-+-" + "-" * 8 + "-+-" + "-" * 10)

    for cat, cm in sorted(result.aggregate_metrics.category_metrics.items()):
        tot = cm.get("total_queries", 0)
        hit_str = f"{cm.get(f'hit_rate@{primary_k}', 0.0) * 100:.1f}%" if cm.get("positive_queries", 0) > 0 else "N/A"
        prec_str = f"{cm.get(f'precision@{primary_k}', 0.0) * 100:.1f}%" if cm.get("positive_queries", 0) > 0 else "N/A"
        rec_str = f"{cm.get(f'recall@{primary_k}', 0.0) * 100:.1f}%" if cm.get("positive_queries", 0) > 0 else "N/A"
        mrr_str = f"{cm.get(f'mrr@{primary_k}', 0.0):.3f}" if cm.get("positive_queries", 0) > 0 else "N/A"
        rej_str = f"{cm.get('correct_rejection_rate', 0.0) * 100:.1f}%" if cm.get("negative_queries", 0) > 0 else "N/A"

        lines.append(f"{cat:<22} | {tot:<6} | {hit_str:<8} | {prec_str:<8} | {rec_str:<8} | {mrr_str:<8} | {rej_str:<10}")
    lines.append("")

    # 4. Detailed Query Diagnosis
    lines.append("4. DETAILED QUERY DIAGNOSIS")
    lines.append(f"{'ID':<8} | {'Category':<16} | {'Status':<14} | {'Top Sim':<8} | {'Retr#':<5} | {'1st Hit Rank':<12} | Question")
    lines.append("-" * 8 + "-+-" + "-" * 16 + "-+-" + "-" * 14 + "-+-" + "-" * 8 + "-+-" + "-" * 5 + "-+-" + "-" * 12 + "-+-" + "-" * 30)

    for q in result.query_details:
        top_sim = f"{q.top_similarity_score:.3f}" if q.top_similarity_score is not None else "0.000"
        hit_rank = str(q.first_hit_rank) if q.first_hit_rank else "-"

        if q.is_negative:
            status = "CORRECT_REJ" if q.correctly_rejected else "FALSE_ALARM"
        else:
            primary_hit = q.is_hit_by_k.get(primary_k, False)
            status = "HIT" if primary_hit else "MISS"

        short_q = q.question[:45] + "..." if len(q.question) > 48 else q.question
        lines.append(f"{q.query_id:<8} | {q.category:<16} | {status:<14} | {top_sim:<8} | {q.retrieved_count:<5} | {hit_rank:<12} | {short_q}")

    lines.append(sep)
    return "\n".join(lines)


def generate_markdown_report(result: EvaluationResult) -> str:
    """
    Renders a formatted GitHub-flavored Markdown report.
    """
    lines = []
    lines.append("# RAG Retrieval Evaluation Report - Apex Ops AI\n")

    if result.is_mock_or_demo:
        lines.append("> [!IMPORTANT]\n"
                     "> **Execution Mode**: `DEMO / MOCK MODE` (Deterministic Offline Embeddings).\n"
                     "> *Results demonstrate retrieval logic and metric tracking without invoking paid external API quotas.*\n")
    else:
        lines.append(f"> [!NOTE]\n"
                     f"> **Execution Mode**: `LIVE PRODUCTION PROVIDER` (`{result.provider}` - `{result.model}`, `{result.dimension}` dimensions).\n")

    lines.append(f"- **Execution Timestamp (UTC)**: `{result.timestamp_utc}`")
    lines.append(f"- **Dataset**: {result.dataset_name} (v{result.dataset_version})")
    lines.append(f"- **Database Backend**: `{result.database_backend}`")
    lines.append(f"- **Relevance Threshold**: `{result.relevance_threshold:.2f}` (Minimum similarity to retrieve)")
    lines.append(f"- **Total Evaluated Questions**: {result.aggregate_metrics.total_queries}")
    lines.append(f"  - Positive Knowledge Base Queries: {result.aggregate_metrics.positive_queries_count}")
    lines.append(f"  - Negative / Unsupported Queries: {result.aggregate_metrics.negative_queries_count}\n")

    # Metrics table
    lines.append("## 1. Retrieval Performance by Cutoff (K)\n")
    lines.append("| K | Hit Rate@K | Standard Precision@K | Effective Precision@K | Recall@K | MRR@K |")
    lines.append("|---|---|---|---|---|---|")
    for k, m in sorted(result.aggregate_metrics.metrics_by_k.items()):
        lines.append(
            f"| **@{k}** | {m.hit_rate * 100:.1f}% | {m.precision * 100:.1f}% | "
            f"{m.effective_precision * 100:.1f}% | {m.recall * 100:.1f}% | {m.mrr:.4f} |"
        )
    lines.append("\n*Note: Standard Precision@K penalizes when fewer than K chunks are returned; Effective Precision@K measures precision over retrieved chunks.*\n")

    # Negative Query Handling
    lines.append("## 2. Negative Query Rejection Performance\n")
    neg = result.aggregate_metrics.negative_metrics
    if neg:
        lines.append(f"- **Total Negative Queries**: {neg.total_negative_queries}")
        lines.append(f"- **Correctly Rejected (True Negatives)**: {neg.correctly_rejected} ({neg.correct_rejection_rate * 100:.1f}%)")
        lines.append(f"- **False Alarms (False Positives)**: {neg.false_positives} ({neg.false_positive_rate * 100:.1f}%)\n")
        lines.append("### Negative Query Audit Table\n")
        lines.append("| ID | Status | Retrieved Count | Top Similarity | Question | Policy Boundary Rationale |")
        lines.append("|---|---|---|---|---|---|")
        for q in result.query_details:
            if not q.is_negative:
                continue
            status_badge = "✅ True Negative" if q.correctly_rejected else "⚠️ False Positive"
            top_sim = f"{q.top_similarity_score:.3f}" if q.top_similarity_score is not None else "-"
            reason = q.negative_reasoning or "Out of scope"
            lines.append(f"| `{q.query_id}` | {status_badge} | {q.retrieved_count} | {top_sim} | {q.question} | {reason} |")
    else:
        lines.append("No negative queries in this dataset.\n")
    lines.append("")

    # Category Breakdown
    lines.append("## 3. Performance by Policy Category\n")
    primary_k = 3 if 3 in result.k_values else (result.k_values[0] if result.k_values else 3)
    lines.append(f"| Category | Queries | Hit@{primary_k} | Precision@{primary_k} | Recall@{primary_k} | MRR@{primary_k} | Rejection Rate |")
    lines.append("|---|---|---|---|---|---|---|")
    for cat, cm in sorted(result.aggregate_metrics.category_metrics.items()):
        tot = cm.get("total_queries", 0)
        hit_str = f"{cm.get(f'hit_rate@{primary_k}', 0.0) * 100:.1f}%" if cm.get("positive_queries", 0) > 0 else "N/A"
        prec_str = f"{cm.get(f'precision@{primary_k}', 0.0) * 100:.1f}%" if cm.get("positive_queries", 0) > 0 else "N/A"
        rec_str = f"{cm.get(f'recall@{primary_k}', 0.0) * 100:.1f}%" if cm.get("positive_queries", 0) > 0 else "N/A"
        mrr_str = f"{cm.get(f'mrr@{primary_k}', 0.0):.3f}" if cm.get("positive_queries", 0) > 0 else "N/A"
        rej_str = f"{cm.get('correct_rejection_rate', 0.0) * 100:.1f}%" if cm.get("negative_queries", 0) > 0 else "N/A"
        lines.append(f"| `{cat}` | {tot} | {hit_str} | {prec_str} | {rec_str} | {mrr_str} | {rej_str} |")
    lines.append("")

    # Query diagnosis table
    lines.append("## 4. Per-Query Diagnosis Details\n")
    lines.append("| ID | Category | Status | 1st Hit Rank | Top Similarity | Target Chunk(s) | Question |")
    lines.append("|---|---|---|---|---|---|---|")
    for q in result.query_details:
        top_sim = f"{q.top_similarity_score:.3f}" if q.top_similarity_score is not None else "-"
        hit_rank = str(q.first_hit_rank) if q.first_hit_rank else "-"
        if q.is_negative:
            status = "✅ True Negative" if q.correctly_rejected else "⚠️ False Positive"
            target_str = "None (Out-of-Scope)"
        else:
            primary_hit = q.is_hit_by_k.get(primary_k, False)
            status = "✅ Hit" if primary_hit else "❌ Miss"
            target_str = ", ".join([f"Chunk {t.chunk_index} ({t.section_title})" for t in q.target_chunks])

        lines.append(f"| `{q.query_id}` | `{q.category}` | {status} | {hit_rank} | {top_sim} | {target_str} | {q.question} |")

    return "\n".join(lines)


def generate_json_report(result: EvaluationResult) -> str:
    """
    Serializes the EvaluationResult into pretty-printed JSON.
    """
    return json.dumps(result.model_dump(), indent=2)
