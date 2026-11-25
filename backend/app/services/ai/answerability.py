import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.logging import logger

ANSWERABILITY_CONFIDENCE_THRESHOLD = 0.60


class AnswerabilityResult(BaseModel):
    """
    Structured output of the answerability verification stage.
    Distinguishes between topic-adjacent chunks and chunks that directly answer the question.
    """
    answerable: bool = Field(..., description="True only if retrieved chunks contain direct evidence answering the question")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score in [0.0, 1.0]")
    supporting_chunks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Subset of retrieved chunks that genuinely support answering the question"
    )
    reason: str = Field(..., description="Clear explanation of why evidence is sufficient or insufficient")
    requires_human_review: bool = Field(
        default=True,
        description="Deterministic flag indicating whether the enquiry must be escalated for human review"
    )
    verification_provider: str = Field(
        default="deterministic_guard",
        description="Provider used for verification: 'gemini', 'demo', or 'deterministic_guard'"
    )


def verify_answerability(
    question: str,
    retrieved_chunks: List[Dict[str, Any]]
) -> AnswerabilityResult:
    """
    Verifies whether the retrieved knowledge-base chunks actually contain sufficient evidence
    to directly answer the customer's question.

    Deterministic Python rules:
    1. Empty retrieval or empty question -> immediately unanswerable (requires_human_review=True).
    2. When active_provider == 'gemini', uses Gemini structured JSON verification.
    3. On any Gemini API error, fails closed (answerable=False, requires_human_review=True).
    4. Post-check: if answerable=True but supporting_chunks is empty or confidence < threshold,
       deterministically overrides to answerable=False.
    """
    if not question or not question.strip():
        return AnswerabilityResult(
            answerable=False,
            confidence=0.0,
            supporting_chunks=[],
            reason="Customer question is empty; cannot verify answerability.",
            requires_human_review=True,
            verification_provider="deterministic_guard"
        )

    if not retrieved_chunks:
        return AnswerabilityResult(
            answerable=False,
            confidence=0.0,
            supporting_chunks=[],
            reason="No knowledge base chunks were retrieved above the relevance threshold.",
            requires_human_review=True,
            verification_provider="deterministic_guard"
        )

    active_provider = settings.active_provider

    if active_provider == "gemini":
        try:
            raw_result = _verify_answerability_gemini(question, retrieved_chunks)
            return _apply_deterministic_guards(raw_result, retrieved_chunks, provider="gemini")
        except Exception as e:
            err_type = type(e).__name__
            logger.error(f"Gemini answerability verification failed with '{err_type}'. Failing closed for human review.")
            return AnswerabilityResult(
                answerable=False,
                confidence=0.0,
                supporting_chunks=[],
                reason="Answerability verification service unavailable; escalated for human review to prevent unsupported claims.",
                requires_human_review=True,
                verification_provider="gemini"
            )

    # Deterministic Demo Mode fallback
    raw_result = _verify_answerability_deterministic_demo(question, retrieved_chunks)
    return _apply_deterministic_guards(raw_result, retrieved_chunks, provider="demo")


def _apply_deterministic_guards(
    parsed_result: Dict[str, Any],
    retrieved_chunks: List[Dict[str, Any]],
    provider: str
) -> AnswerabilityResult:
    """
    Enforces deterministic Python consistency rules on the verification output.
    """
    answerable = bool(parsed_result.get("answerable", False))
    try:
        confidence = float(parsed_result.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, round(confidence, 4)))

    reason = str(parsed_result.get("reason", "")).strip() or "No reason provided."
    raw_indices = parsed_result.get("supporting_chunk_indices", [])

    # Map valid 0-based indices back to actual retrieved chunk dicts (deduplicated)
    supporting_chunks: List[Dict[str, Any]] = []
    seen_indices = set()
    if isinstance(raw_indices, list):
        for idx in raw_indices:
            if isinstance(idx, int) and 0 <= idx < len(retrieved_chunks) and idx not in seen_indices:
                seen_indices.add(idx)
                supporting_chunks.append(retrieved_chunks[idx])

    # Consistency guards: cannot claim answerable without supporting chunks or sufficient confidence
    if answerable and not supporting_chunks:
        answerable = False
        reason = f"Overridden to unanswerable: verification returned no supporting chunks. ({reason})"
    elif answerable and confidence < ANSWERABILITY_CONFIDENCE_THRESHOLD:
        answerable = False
        supporting_chunks = []
        reason = (
            f"Overridden to unanswerable: confidence {confidence:.2f} is below "
            f"minimum threshold {ANSWERABILITY_CONFIDENCE_THRESHOLD:.2f}. ({reason})"
        )

    if not answerable:
        supporting_chunks = []

    requires_human_review = not answerable

    return AnswerabilityResult(
        answerable=answerable,
        confidence=confidence,
        supporting_chunks=supporting_chunks,
        reason=reason,
        requires_human_review=requires_human_review,
        verification_provider=provider
    )


def _verify_answerability_gemini(
    question: str,
    retrieved_chunks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Uses Google Gemini with structured JSON output to verify whether retrieved chunks
    directly answer the customer's question vs. merely sharing related topic keywords.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    formatted_chunks = []
    for idx, chunk in enumerate(retrieved_chunks):
        title = chunk.get("document_title", "Unknown Document")
        c_idx = chunk.get("chunk_index", 0)
        score = chunk.get("similarity_score", 0.0)
        content = chunk.get("content", "")
        formatted_chunks.append(
            f"[Chunk {idx}] Document: {title} (Section/Chunk #{c_idx}, Similarity: {score})\n{content}"
        )

    chunks_block = "\n\n".join(formatted_chunks)

    system_instruction = (
        "You are a strict factual verification judge for Apex Operations Inc. customer support.\n"
        "Your ONLY job is to determine whether the retrieved knowledge-base chunks contain "
        "DIRECT, EXPLICIT evidence to answer the customer's specific question.\n\n"
        "CRITICAL DISTINCTION:\n"
        "- 'Semantically related' is NOT 'answerable'.\n"
        "- For example, if a customer asks about German customs VAT fees, a chunk about continental FedEx Ground shipping is RELATED to shipping, "
        "but DOES NOT answer the question -> answerable MUST be false.\n"
        "- If a customer asks about Klarna/Affirm installments, a chunk about refunding to the original payment method is RELATED to payments, "
        "but DOES NOT answer the question -> answerable MUST be false.\n"
        "- If a customer asks about in-store Chicago pickup, a chunk about courier tracking or return warehouses DOES NOT answer the question -> answerable MUST be false.\n"
        "- Only return answerable=true if the retrieved chunks explicitly contain the facts needed to answer the question without guessing or extrapolating.\n\n"
        "Return a valid JSON object with keys:\n"
        "- 'answerable': boolean\n"
        "- 'confidence': float between 0.0 and 1.0\n"
        "- 'supporting_chunk_indices': list of integer indices (e.g. [0, 2]) from [Chunk 0], [Chunk 1], ... that directly answer the question. Empty list [] if answerable is false.\n"
        "- 'reason': concise explanation of why the chunks directly answer the question or why they are merely related/insufficient."
    )

    prompt = (
        f"CUSTOMER QUESTION:\n{question}\n\n"
        f"RETRIEVED KNOWLEDGE BASE CHUNKS:\n{chunks_block}\n\n"
        "Evaluate answerability strictly and output JSON."
    )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        temperature=0.0,
        max_output_tokens=512
    )

    response = client.models.generate_content(
        model=settings.LLM_MODEL,
        contents=prompt,
        config=config
    )

    return json.loads(response.text or "{}")


def _verify_answerability_deterministic_demo(
    question: str,
    retrieved_chunks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Deterministic offline verification heuristic for Demo Mode.
    Checks for high similarity and out-of-scope unsupported topic markers.
    """
    q_lower = question.lower()

    # Known out-of-scope / unsupported policy markers in deterministic mode
    unsupported_markers = [
        "customs", "vat", "germany", "import duty",
        "physical retail store", "chicago", "in-person pickup",
        "trade-in", "recycling",
        "price-match", "price match", "best buy", "amazon",
        "klarna", "affirm", "monthly installments",
        "self-service portal", "5 minutes after placing"
    ]
    for marker in unsupported_markers:
        if marker in q_lower:
            return {
                "answerable": False,
                "confidence": 0.15,
                "supporting_chunk_indices": [],
                "reason": f"Demo verifier detected unsupported topic ('{marker}') not covered by retrieved policy chunks."
            }

    # Check if top chunk has meaningful similarity
    supporting = []
    max_sim = 0.0
    for idx, chunk in enumerate(retrieved_chunks):
        sim = float(chunk.get("similarity_score", 0.0))
        if sim > max_sim:
            max_sim = sim
        if sim >= 0.35:
            supporting.append(idx)

    if supporting and max_sim >= 0.35:
        return {
            "answerable": True,
            "confidence": min(0.95, round(max_sim + 0.25, 2)),
            "supporting_chunk_indices": supporting,
            "reason": "Retrieved knowledge base chunks meet deterministic evidence criteria."
        }

    return {
        "answerable": False,
        "confidence": round(max_sim, 2),
        "supporting_chunk_indices": [],
        "reason": "Retrieved chunks have insufficient similarity to directly answer the customer question."
    }
