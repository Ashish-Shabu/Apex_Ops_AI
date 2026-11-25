from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from backend.app.core.database import get_db
from backend.app.models.enquiry import Enquiry, EnquiryStatus, EnquiryCategory, EnquiryPriority
from backend.app.models.draft import ResponseDraft, DraftStatus
from backend.app.schemas.enquiry import EnquiryCreate, EnquiryUpdate, EnquiryResponse, EnquiryDetailResponse
from backend.app.schemas.draft import ResponseDraftCreate, ResponseDraftReview, ResponseDraftResponse
from backend.app.schemas.ai import AIClassificationResult, AIDraftGenerationRequest, AIDraftGenerationResult
from backend.app.services.ai.llm_client import llm_client
from backend.app.services.ai.rag import search_knowledge_base
from backend.app.services.ai.embeddings import EmbeddingMismatchError, EmbeddingProviderError
from backend.app.services.ai.answerability import verify_answerability
from backend.app.services.audit_service import record_audit_log
from backend.app.core.logging import logger

router = APIRouter(prefix="/enquiries", tags=["Enquiries"])


@router.get("", response_model=List[EnquiryResponse])
def list_enquiries(
    db: Session = Depends(get_db),
    status: Optional[EnquiryStatus] = None,
    category: Optional[EnquiryCategory] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """List customer enquiries with filtering and pagination."""
    query = db.query(Enquiry)

    if status:
        query = query.filter(Enquiry.status == status)
    if category:
        query = query.filter(Enquiry.category == category)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Enquiry.customer_name.ilike(search_fmt),
                Enquiry.customer_email.ilike(search_fmt),
                Enquiry.subject.ilike(search_fmt),
                Enquiry.order_number.ilike(search_fmt)
            )
        )

    enquiries = query.order_by(desc(Enquiry.created_at)).offset(skip).limit(limit).all()
    
    # Enrich with draft counts and latest draft ID
    results = []
    for enq in enquiries:
        drafts = enq.drafts
        resp = EnquiryResponse.model_validate(enq)
        resp.drafts_count = len(drafts)
        resp.latest_draft_id = drafts[0].id if drafts else None
        results.append(resp)

    return results


@router.post("", response_model=EnquiryDetailResponse, status_code=status.HTTP_201_CREATED)
def create_enquiry(enquiry_in: EnquiryCreate, db: Session = Depends(get_db)):
    """
    Create a new customer enquiry.
    Automatically triggers AI classification and summarization.
    """
    enquiry = Enquiry(
        customer_name=enquiry_in.customer_name,
        customer_email=enquiry_in.customer_email,
        channel=enquiry_in.channel,
        subject=enquiry_in.subject,
        message=enquiry_in.message,
        order_number=enquiry_in.order_number,
        status=EnquiryStatus.PENDING
    )
    db.add(enquiry)
    db.flush()

    record_audit_log(
        db=db,
        action="enquiry_created",
        actor=f"customer:{enquiry.customer_email}",
        enquiry_id=enquiry.id,
        details={"channel": enquiry.channel, "subject": enquiry.subject}
    )

    # Perform automated AI classification and summarization
    try:
        classification = llm_client.classify_and_summarize(
            customer_name=enquiry.customer_name,
            subject=enquiry.subject,
            message=enquiry.message
        )
        enquiry.category = EnquiryCategory(classification.get("category", "general_support"))
        enquiry.priority = EnquiryPriority(classification.get("priority", "medium"))
        enquiry.sentiment = classification.get("sentiment", "neutral")
        enquiry.ai_summary = classification.get("summary")
        enquiry.ai_confidence = float(classification.get("confidence", 0.9))
        
        # If user didn't provide order number but AI detected one
        if not enquiry.order_number and classification.get("order_number_detected"):
            enquiry.order_number = classification["order_number_detected"]

        record_audit_log(
            db=db,
            action="ai_classified",
            actor="ai_engine",
            enquiry_id=enquiry.id,
            details={
                "category": enquiry.category.value,
                "priority": enquiry.priority.value,
                "sentiment": enquiry.sentiment,
                "is_demo_mode": classification.get("is_demo_mode", True)
            }
        )
    except Exception as e:
        logger.error(f"Automatic classification error on enquiry {enquiry.id}: {e}")
        # Graceful fallback: defaults are already intact
        enquiry.ai_summary = "Auto-classification failed. Enquiry awaiting staff review."

    db.commit()
    db.refresh(enquiry)
    return _build_enquiry_detail(enquiry)


@router.get("/{enquiry_id}", response_model=EnquiryDetailResponse)
def get_enquiry(enquiry_id: int, db: Session = Depends(get_db)):
    """Retrieve an enquiry with its drafts and audit trail."""
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail=f"Enquiry {enquiry_id} not found")
    return _build_enquiry_detail(enquiry)


@router.patch("/{enquiry_id}", response_model=EnquiryDetailResponse)
def update_enquiry(enquiry_id: int, payload: EnquiryUpdate, db: Session = Depends(get_db)):
    """Update enquiry status, category, priority, or details."""
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail=f"Enquiry {enquiry_id} not found")

    updated_fields = {}
    for field, val in payload.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(enquiry, field, val)
            updated_fields[field] = str(val)

    record_audit_log(
        db=db,
        action="enquiry_updated",
        actor="staff_user",
        enquiry_id=enquiry.id,
        details=updated_fields
    )

    db.commit()
    db.refresh(enquiry)
    return _build_enquiry_detail(enquiry)


@router.post("/{enquiry_id}/classify", response_model=AIClassificationResult)
def reclassify_enquiry(enquiry_id: int, db: Session = Depends(get_db)):
    """Trigger manual re-classification of an enquiry."""
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    res = llm_client.classify_and_summarize(
        customer_name=enquiry.customer_name,
        subject=enquiry.subject,
        message=enquiry.message
    )

    enquiry.category = EnquiryCategory(res.get("category", "general_support"))
    enquiry.priority = EnquiryPriority(res.get("priority", "medium"))
    enquiry.sentiment = res.get("sentiment", "neutral")
    enquiry.ai_summary = res.get("summary")
    enquiry.ai_confidence = float(res.get("confidence", 0.9))

    if not enquiry.order_number and res.get("order_number_detected"):
        enquiry.order_number = res["order_number_detected"]

    record_audit_log(
        db=db,
        action="ai_reclassified",
        actor="staff_user",
        enquiry_id=enquiry.id,
        details={"category": enquiry.category.value, "confidence": enquiry.ai_confidence}
    )

    db.commit()

    return AIClassificationResult(
        category=enquiry.category,
        priority=enquiry.priority,
        sentiment=enquiry.sentiment,
        summary=enquiry.ai_summary or "",
        order_number_detected=enquiry.order_number,
        confidence=enquiry.ai_confidence,
        key_entities=res.get("key_entities", [])
    )


@router.post("/{enquiry_id}/draft", response_model=ResponseDraftResponse)
def generate_draft_response(
    enquiry_id: int,
    request: Optional[AIDraftGenerationRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Generate an AI response draft grounded in RAG knowledge base and backend order tools.
    Updates the enquiry status to awaiting_approval.
    """
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    # 1. RAG knowledge search
    query_text = f"{enquiry.subject} {enquiry.message}"
    try:
        retrieved_chunks, has_sufficient = search_knowledge_base(db, query_text, top_k=3)
    except EmbeddingMismatchError as e:
        logger.error(f"Draft generation knowledge retrieval blocked by embedding mismatch: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except EmbeddingProviderError as e:
        logger.error(f"Draft generation knowledge retrieval failed due to provider error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider service is unavailable for knowledge retrieval."
        )

    # 2. Answerability Verification Stage
    answerability = verify_answerability(
        question=query_text,
        retrieved_chunks=retrieved_chunks
    )

    # Strictly pass only verified supporting chunks to draft generation
    if answerability.answerable:
        verified_chunks = answerability.supporting_chunks
        verified_has_sufficient = True
    else:
        verified_chunks = []
        verified_has_sufficient = False

    # 3. Call LLM draft generator with tools and verified chunks
    staff_notes = request.staff_notes if request else None
    draft_result = llm_client.generate_response_draft(
        enquiry_data={
            "customer_name": enquiry.customer_name,
            "customer_email": enquiry.customer_email,
            "subject": enquiry.subject,
            "message": enquiry.message,
            "category": enquiry.category.value,
            "order_number": enquiry.order_number
        },
        retrieved_chunks=verified_chunks,
        has_sufficient_knowledge=verified_has_sufficient,
        db=db,
        staff_notes=staff_notes
    )

    # Check if an order lookup tool found a verified order
    order_resolved = any(
        t.get("tool_name") == "lookup_order" and t.get("result", {}).get("found", False)
        for t in draft_result.get("tools_executed", [])
    )

    # 4. Escalate if insufficient policy evidence AND no verified order resolved the enquiry
    needs_escalation = (not answerability.answerable) and (not order_resolved)

    if needs_escalation:
        # Deterministic Python safety guard: ensure no unsupported policy claims reach customer draft
        safe_draft_body = (
            f"Dear {enquiry.customer_name},\n\n"
            f"Thank you for contacting Apex Operations support regarding \"{enquiry.subject}\".\n\n"
            "Our automated knowledge base does not contain sufficient verified policy information to "
            "fully answer your specific request. To ensure you receive accurate guidance, I have "
            "escalated your enquiry to a support specialist for human review.\n\n"
            "A team member will review your inquiry and follow up with you shortly.\n\n"
            "Warm regards,\n"
            "Customer Operations Team"
        )
        draft_result["draft_body"] = safe_draft_body
        draft_result["rationale"] = (
            f"[HUMAN REVIEW ESCALATION] Answerability check failed "
            f"(confidence={answerability.confidence:.2f}, provider={answerability.verification_provider}): "
            f"{answerability.reason}"
        )
        draft_result["sources_used"] = []

    # 5. Save draft to DB
    draft = ResponseDraft(
        enquiry_id=enquiry.id,
        draft_body=draft_result["draft_body"],
        rationale=draft_result["rationale"],
        retrieved_sources=draft_result["sources_used"],
        tool_calls_used=draft_result["tools_executed"],
        status=DraftStatus.PENDING_REVIEW,
        order_product_mismatch=draft_result.get("order_product_mismatch", False),
        mismatch_details=draft_result.get("mismatch_details", {}),
        answerability_details={
            "answerable": answerability.answerable,
            "confidence": answerability.confidence,
            "supporting_chunk_ids": [c.get("chunk_id") for c in answerability.supporting_chunks],
            "reason": answerability.reason,
            "requires_human_review": needs_escalation,
            "verification_provider": answerability.verification_provider
        }
    )
    db.add(draft)

    # Update enquiry status: IN_REVIEW if escalated for human review, else AWAITING_APPROVAL
    if needs_escalation:
        enquiry.status = EnquiryStatus.IN_REVIEW
        record_audit_log(
            db=db,
            action="answerability_insufficient_escalated",
            actor="answerability_verifier",
            enquiry_id=enquiry.id,
            details={
                "answerable": answerability.answerable,
                "confidence": answerability.confidence,
                "reason": answerability.reason,
                "raw_retrieved_count": len(retrieved_chunks),
                "verification_provider": answerability.verification_provider
            }
        )
    else:
        enquiry.status = EnquiryStatus.AWAITING_APPROVAL

    # Record mismatch in audit log if flagged (Requirement 7)
    if draft_result.get("order_product_mismatch"):
        record_audit_log(
            db=db,
            action="order_product_mismatch_flagged",
            actor="ai_order_validator",
            enquiry_id=enquiry.id,
            details=draft_result.get("mismatch_details", {})
        )

    record_audit_log(
        db=db,
        action="draft_generated",
        actor="ai_assistant",
        enquiry_id=enquiry.id,
        details={
            "sources_count": len(draft_result["sources_used"]),
            "tools_count": len(draft_result["tools_executed"]),
            "is_demo_mode": draft_result["is_demo_mode"],
            "order_product_mismatch": draft_result.get("order_product_mismatch", False)
        }
    )

    db.commit()
    db.refresh(draft)
    return draft


@router.post("/{enquiry_id}/drafts/{draft_id}/review", response_model=ResponseDraftResponse)
def review_draft(
    enquiry_id: int,
    draft_id: int,
    review_in: ResponseDraftReview,
    db: Session = Depends(get_db)
):
    """
    Staff review action: approve, edit and approve, or reject draft.
    Does NOT automatically send customer emails, allowing safe manual or staged dispatch.
    """
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    draft = db.query(ResponseDraft).filter(
        ResponseDraft.id == draft_id,
        ResponseDraft.enquiry_id == enquiry_id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    draft.reviewed_by = review_in.reviewed_by
    draft.reviewed_at = now
    draft.review_feedback = review_in.review_feedback

    if review_in.status == DraftStatus.APPROVED:
        draft.status = DraftStatus.APPROVED
        enquiry.status = EnquiryStatus.RESOLVED
        action = "draft_approved"
    elif review_in.status == DraftStatus.EDITED_AND_APPROVED:
        draft.status = DraftStatus.EDITED_AND_APPROVED
        if review_in.edited_draft_body:
            draft.draft_body = review_in.edited_draft_body
        enquiry.status = EnquiryStatus.RESOLVED
        action = "draft_edited_and_approved"
    elif review_in.status == DraftStatus.REJECTED:
        draft.status = DraftStatus.REJECTED
        enquiry.status = EnquiryStatus.IN_REVIEW
        action = "draft_rejected"
    else:
        raise HTTPException(status_code=400, detail="Invalid review status")

    record_audit_log(
        db=db,
        action=action,
        actor=f"staff:{review_in.reviewed_by}",
        enquiry_id=enquiry.id,
        details={
            "feedback": review_in.review_feedback,
            "new_enquiry_status": enquiry.status.value
        }
    )

    db.commit()
    db.refresh(draft)
    return draft


def _build_enquiry_detail(enquiry: Enquiry) -> EnquiryDetailResponse:
    resp = EnquiryDetailResponse.model_validate(enquiry)
    resp.drafts_count = len(enquiry.drafts)
    resp.latest_draft_id = enquiry.drafts[0].id if enquiry.drafts else None
    return resp
