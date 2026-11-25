import pytest
from backend.app.services.ai.text_utils import (
    deduplicate_repetitive_words,
    format_policy_context,
    sanitize_draft_response,
    enforce_mismatch_privacy
)
from backend.app.services.ai.order_validator import OrderValidationResult


def test_deduplicate_repetitive_words_prepaid():
    """Verify that duplicated pre-paid/prepaid modifier variants are eliminated."""
    # Pre-paid prepaid
    t1 = "Apex Operations provides a complimentary pre-paid prepaid shipping return label."
    res1 = deduplicate_repetitive_words(t1)
    assert res1 == "Apex Operations provides a complimentary pre-paid shipping return label."

    # Prepaid pre-paid
    t2 = "We will send a prepaid pre-paid label for your parcel."
    res2 = deduplicate_repetitive_words(t2)
    assert res2 == "We will send a pre-paid label for your parcel."

    # Other duplicate adjectives and words
    t3 = "Please enjoy this complimentary free replacement."
    res3 = deduplicate_repetitive_words(t3)
    assert res3 == "Please enjoy this complimentary replacement."

    t4 = "We checked the the tracking details."
    res4 = deduplicate_repetitive_words(t4)
    assert res4 == "We checked the tracking details."


def test_format_policy_context_preserves_complete_content():
    """Requirement: Preserve complete relevant policy context wherever possible."""
    policy_chunk = (
        "3. Pre-paid Return Labels\n"
        "For all defective items or orders received in damaged condition, Apex Operations provides "
        "a complimentary pre-paid prepaid shipping return label. For voluntary returns (e.g. change of mind), "
        "a flat return shipping fee of $7.50 is deducted from the refund total."
    )
    formatted = format_policy_context(policy_chunk)

    # 1. Duplicated wording is resolved
    assert "pre-paid prepaid" not in formatted
    assert "pre-paid shipping return label" in formatted

    # 2. Both defective and voluntary policies are completely preserved
    assert "defective items" in formatted
    assert "voluntary returns" in formatted
    assert "$7.50 is deducted from the refund total" in formatted

    # 3. No truncation or broken words
    assert not formatted.endswith("a f...")
    assert not formatted.endswith("...")


def test_format_policy_context_graceful_sentence_boundary_when_limit_applied():
    """
    Requirement: If context limits are reached, handle them gracefully instead of silently cutting text mid-sentence.
    """
    policy_chunk = (
        "3. Pre-paid Return Labels\n"
        "For all defective items or orders received in damaged condition, Apex Operations provides "
        "a complimentary pre-paid shipping return label. For voluntary returns (e.g. change of mind), "
        "a flat return shipping fee of $7.50 is deducted from the refund total."
    )
    # Applying a 220 character limit should end cleanly at the end of the first complete sentence,
    # never truncating mid-word ('a f...') or cutting mid-clause.
    truncated = format_policy_context(policy_chunk, max_chars=220)

    assert not truncated.endswith("a f...")
    assert not truncated.endswith("f...")
    assert "For all defective items or orders received in damaged condition" in truncated
    assert truncated.endswith(".")


def test_sanitize_draft_response_cleans_dangling_truncation():
    """Verify draft sanitizer removes dangling truncated words or incomplete quotes."""
    bad_draft = (
        "Dear Rahul Nair,\n\n"
        "General Policy Information:\n"
        "• Per our Customer Return and Refund Policy:\n"
        "  \"3. Pre-paid Return Labels\n"
        "For all defective items or orders received in damaged condition, Apex Operations provides "
        "a complimentary pre-paid prepaid shipping return label. For voluntary returns (e.g. change of mind), a f...\""
    )

    sanitized = sanitize_draft_response(bad_draft)

    # Must eliminate duplicate modifier
    assert "pre-paid prepaid" not in sanitized
    # Must eliminate dangling "a f..."
    assert "a f..." not in sanitized


def test_enforce_mismatch_privacy_scrubs_actual_product_names():
    """
    Requirement 9: Test that customer-facing draft does not reveal the other product,
    while internal validation result retains details.
    """
    val_result = OrderValidationResult(
        is_validated=True,
        has_mismatch=True,
        is_match=False,
        order_number="ORD-1001",
        customer_mentioned_terms=["keyboard"],
        order_actual_products=["Apex Ergonomic Mesh Desk Chair"],
        matching_products=[],
        reason="Product mismatch detected: Customer enquiry refers to 'keyboard', but order ORD-1001 contains: 'Apex Ergonomic Mesh Desk Chair'."
    )

    leaky_draft = (
        "Dear Customer,\n\n"
        "Important Notice Regarding Order ORD-1001:\n"
        "We checked order ORD-1001 and found it is for an Apex Ergonomic Mesh Desk Chair, not a keyboard.\n"
        "Please check your order number.\n\n"
        "Warm regards,\nCustomer Support"
    )

    clean_draft = enforce_mismatch_privacy(leaky_draft, val_result)

    # 1. Must NOT reveal the other product
    assert "Chair" not in clean_draft
    assert "Desk Chair" not in clean_draft
    assert "Apex Ergonomic Mesh Desk Chair" not in clean_draft

    # 2. Must state that order details could not be verified
    assert "could not be verified" in clean_draft.lower()

    # 3. Must request verification via order number or checkout email
    assert "order number" in clean_draft.lower()
    assert "checkout email" in clean_draft.lower() or "purchase receipt" in clean_draft.lower()


def test_enforce_mismatch_privacy_noop_on_matching_order():
    """Requirement 9: Test that matching orders continue to work normally and are not modified."""
    match_result = OrderValidationResult(
        is_validated=True,
        has_mismatch=False,
        is_match=True,
        order_number="ORD-1002",
        customer_mentioned_terms=["keyboard"],
        order_actual_products=["Apex Pro Wireless Mechanical Keyboard"],
        matching_products=["Apex Pro Wireless Mechanical Keyboard"],
        reason="Matched product 'Apex Pro Wireless Mechanical Keyboard' in order ORD-1002."
    )

    normal_draft = (
        "Dear Customer,\n\n"
        "We found your order ORD-1002 with Apex Pro Wireless Mechanical Keyboard.\n"
        "Status: In Transit."
    )

    res = enforce_mismatch_privacy(normal_draft, match_result)
    assert res == normal_draft
    assert "Apex Pro Wireless Mechanical Keyboard" in res

