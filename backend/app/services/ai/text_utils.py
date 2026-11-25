import re
from typing import Optional, Any, List


def deduplicate_repetitive_words(text: str) -> str:
    """
    Detects and eliminates duplicated adjacent words or repetitive modifier pairs
    such as 'pre-paid prepaid', 'prepaid pre-paid', 'free complimentary', 'the the', etc.,
    preserving grammatical correctness and policy terms.
    """
    if not text:
        return ""

    # Specific common modifier/adjective duplicates
    cleaned = re.sub(
        r"\bpre-paid\s+prepaid\b", "pre-paid", text, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"\bprepaid\s+pre-paid\b", "pre-paid", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"\bprepaid\s+prepaid\b", "prepaid", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"\bpre-paid\s+pre-paid\b", "pre-paid", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"\bcomplimentary\s+free\b", "complimentary", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"\bfree\s+complimentary\b", "complimentary", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"\brefund\s+back\b", "refund", cleaned, flags=re.IGNORECASE
    )

    # General consecutive identical words (e.g. 'the the', 'and and', 'is is')
    cleaned = re.sub(
        r"\b([A-Za-z]+)\s+\1\b",
        r"\1",
        cleaned,
        flags=re.IGNORECASE
    )

    # Clean multiple spaces while preserving newlines
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def format_policy_context(content: str, max_chars: Optional[int] = None) -> str:
    """
    Formats policy context to preserve complete relevant policy meaning.
    Deduplicates repetitive words and normalizes formatting.
    If max_chars is provided and text exceeds it, gracefully truncates at the last
    complete sentence boundary rather than chopping mid-word or mid-sentence.
    """
    if not content:
        return ""

    cleaned = deduplicate_repetitive_words(content)

    if max_chars is None or len(cleaned) <= max_chars:
        return cleaned

    # Context exceeds max_chars: gracefully truncate at complete sentence boundary
    truncated_candidate = cleaned[:max_chars]

    # Protect abbreviations (e.g., i.e.) and bullet numbers (e.g. 1., 2.) from false sentence ends
    # Use single-char replacement so string length and indices remain 1:1 identical with cleaned
    protected = re.sub(r"\b(e\.g\.|i\.e\.)", lambda m: m.group(1).replace(".", "\x00"), truncated_candidate)
    protected = re.sub(r"(?:^|\n)\s*(\d+)\.", lambda m: m.group(0)[:-1] + "\x00", protected)

    # Find genuine sentence ends (.!?) followed by space, newline, or end of string
    sentence_matches = list(re.finditer(r"[.!?](?:\s+|$)", protected))

    # If a sentence boundary exists and preserves at least 40% of the allowed context
    if sentence_matches and sentence_matches[-1].end() >= int(max_chars * 0.4):
        end_idx = sentence_matches[-1].end()
        result = cleaned[:end_idx].strip()
        return result

    # Fallback: break at the last whitespace to avoid mid-word truncation (never produce 'a f...')
    last_space = truncated_candidate.rfind(" ")
    if last_space > int(max_chars * 0.3):
        return truncated_candidate[:last_space].rstrip(" ,;:-") + "..."

    return truncated_candidate.strip() + "..."


def sanitize_draft_response(draft_body: str) -> str:
    """
    Sanitizes customer-facing draft responses:
    - Removes duplicated phrasing or repetitive words.
    - Cleans up any trailing broken sentences or mid-word ellipses (e.g. '... a f...').
    - Normalizes spacing.
    """
    if not draft_body:
        return ""

    sanitized = deduplicate_repetitive_words(draft_body)

    # Detect and clean dangling mid-word truncations like '... a f...' or 'a f...' at the end of quotes or text
    sanitized = re.sub(
        r'(?:,\s*)?\b[a-zA-Z]{1,2}\s*\.\.\.\s*"?$',
        '',
        sanitized
    ).strip()

    return sanitized


def enforce_mismatch_privacy(
    draft_body: str,
    validation_result: Optional[Any]
) -> str:
    """
    Ensures that customer-facing drafts NEVER reveal the actual product names,
    quantities, prices, or sensitive items from a mismatched order.

    If an order-product mismatch was detected:
    1. Replaces any accidental mention of actual mismatched product names or forbidden
       product keywords with privacy-safe references.
    2. Ensures the draft clearly states that order details could not be verified
       against the product mentioned, and requests verification via order number or checkout email.
    """
    if not validation_result or not getattr(validation_result, "has_mismatch", False):
        return draft_body

    sanitized = draft_body
    order_num = getattr(validation_result, "order_number", None) or "provided"
    actual_products = getattr(validation_result, "order_actual_products", []) or []
    customer_terms = getattr(validation_result, "customer_mentioned_terms", []) or []

    # 1. Redact any accidental mentions of the actual mismatched product names
    for prod in actual_products:
        if not prod:
            continue
        pattern = re.compile(re.escape(prod), re.IGNORECASE)
        sanitized = pattern.sub("[confidential order item]", sanitized)

    # 2. Check generic product taxonomy keywords of the actual product that customer didn't mention
    from backend.app.services.ai.order_validator import PRODUCT_TAXONOMY
    cust_terms_lower = [t.lower() for t in customer_terms]

    forbidden_keywords = set()
    for prod in actual_products:
        lower_prod = prod.lower()
        for cat, kws in PRODUCT_TAXONOMY.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', lower_prod) for kw in kws):
                # Only forbid if customer did not enquire about this category
                if not any(kw in cust_terms_lower for kw in kws):
                    for kw in kws:
                        if len(kw) > 3:
                            forbidden_keywords.add(kw)

    for kw in forbidden_keywords:
        pattern = re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
        sanitized = pattern.sub("[item]", sanitized)

    # 3. Standard privacy-safe notice
    standard_notice = (
        f"Important Notice Regarding Order {order_num}:\n"
        "The provided order details could not be verified against the product mentioned in your enquiry.\n"
        "For your security and privacy, could you please double-check your order number from your purchase receipt, "
        "or confirm the registered checkout email address so our support team can verify and locate your order?"
    )

    # 4. If the draft had an "Important Notice Regarding Order" block leaking details or contains redacted placeholders,
    # replace that block with the standard notice
    notice_pattern = re.compile(
        rf"Important Notice Regarding Order {re.escape(order_num)}:[^\n]*\n(?:[^\n]+\n)*?(?=(?:General Policy Information|\n\w|\n\n|$))",
        re.IGNORECASE
    )
    if notice_pattern.search(sanitized):
        sanitized = notice_pattern.sub(standard_notice + "\n\n", sanitized)
    elif "[confidential order item]" in sanitized or "[item]" in sanitized or "could not be verified" not in sanitized.lower():
        # Clean any remaining placeholders
        sanitized = sanitized.replace("[confidential order item]", "an item")
        sanitized = sanitized.replace("[item]", "an item")
        # Ensure standard notice is present
        if "could not be verified" not in sanitized.lower():
            sanitized = standard_notice + "\n\n" + sanitized

    # Final sweep: Ensure no actual product name is in sanitized (case-insensitive)
    for prod in actual_products:
        if prod and prod.lower() in sanitized.lower():
            sanitized = re.sub(re.escape(prod), "an item", sanitized, flags=re.IGNORECASE)

    # Ensure no forbidden keywords remain in sanitized
    for kw in forbidden_keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', sanitized, flags=re.IGNORECASE):
            sanitized = re.sub(r'\b' + re.escape(kw) + r'\b', "an item", sanitized, flags=re.IGNORECASE)

    return sanitized.strip()
