import argparse
import sys
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal, init_db
from backend.app.models.document import Document, DocumentChunk
from backend.app.seed_data import seed_database
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.evaluation.evaluator import RAGEvaluator, EvaluationResult
from backend.app.evaluation.dataset import get_default_evaluation_dataset
from backend.app.evaluation.reporter import (
    generate_text_report,
    generate_markdown_report,
    generate_json_report
)


def run_evaluation(
    db: Optional[Session] = None,
    k_values: Optional[List[int]] = None,
    output_format: str = "text",
    output_file: Optional[str] = None,
    reindex: bool = False
) -> EvaluationResult:
    """
    Executes the RAG evaluation framework against the active knowledge base.
    """
    k_vals = k_values or [1, 3, 5]
    close_db = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_db = True

    try:
        # Check if database has documents; if not, seed sample documents
        doc_count = db.query(Document).count()
        chunk_count = db.query(DocumentChunk).filter(DocumentChunk.embedding.isnot(None)).count()
        if doc_count == 0 or chunk_count == 0:
            logger.info("Knowledge base is empty. Seeding initial documents for evaluation...")
            seed_database(db)

        # Check if stored chunks have missing metadata or if user requested explicit reindex
        missing_metadata = db.query(DocumentChunk).filter(
            DocumentChunk.embedding.isnot(None),
            DocumentChunk.embedding_provider.is_(None)
        ).count()
        if missing_metadata > 0 or reindex:
            logger.info("Knowledge base chunks require indexing to active configuration. Re-indexing...")
            from backend.app.api.v1.documents import reindex_all_documents
            reindex_all_documents(db)

        dataset = get_default_evaluation_dataset()
        evaluator = RAGEvaluator(db=db, dataset=dataset, k_values=k_vals)
        result = evaluator.run()

        # Render report
        if output_format == "markdown":
            report_content = generate_markdown_report(result)
        elif output_format == "json":
            report_content = generate_json_report(result)
        else:
            report_content = generate_text_report(result)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report_content)
            logger.info(f"Evaluation report written to {output_file}")
        else:
            print(report_content)

        return result
    finally:
        if close_db:
            db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Apex Ops AI - RAG Retrieval Evaluation Runner"
    )
    parser.add_argument(
        "--k",
        type=str,
        default="1,3,5",
        help="Comma-separated cutoff values for K (e.g. '1,3,5' or '3')"
    )
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output report format (default: text)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write the evaluation report"
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force re-indexing of knowledge base documents before evaluation"
    )

    args = parser.parse_args()
    try:
        k_values = [int(x.strip()) for x in args.k.split(",") if x.strip()]
    except ValueError:
        print("Error: --k must be comma-separated integers e.g. '1,3,5'")
        sys.exit(1)

    run_evaluation(
        k_values=k_values,
        output_format=args.format,
        output_file=args.output,
        reindex=args.reindex
    )


if __name__ == "__main__":
    main()
