from typing import List, Optional
from pydantic import BaseModel, Field


class TargetChunkReference(BaseModel):
    """
    Explicit ground-truth reference to a specific chunk in the knowledge base.
    """
    document_file: str = Field(..., description="File name of the document, e.g. 'return_refund_policy.txt'")
    document_title: str = Field(..., description="Title of the document, e.g. 'Customer Return and Refund Policy'")
    chunk_index: int = Field(..., description="0-indexed position of the chunk within the document")
    section_title: str = Field(..., description="Section heading within the chunk, e.g. '1. Eligibility Window'")
    rationale: str = Field(..., description="Explicit reasoning explaining how this chunk directly answers the question")


class EvaluationQuery(BaseModel):
    """
    Schema for a customer query in the RAG evaluation dataset.
    """
    id: str = Field(..., description="Unique query identifier (e.g. eval-01)")
    question: str = Field(..., description="Realistic customer support query")
    category: str = Field(..., description="Policy domain: refunds, shipping, cancellations, returns, warranties, order_policies, negative_unsupported")
    target_chunks: List[TargetChunkReference] = Field(
        default_factory=list,
        description="Explicit ground-truth chunk references that answer the question. Empty for negative queries."
    )
    ground_truth_answer: str = Field(
        ...,
        description="Concise summary of the verified policy answer according to the knowledge base."
    )
    is_negative: bool = Field(
        default=False,
        description="True if no relevant information exists in the knowledge base (unsupported / out-of-scope question)."
    )
    negative_reasoning: Optional[str] = Field(
        default=None,
        description="For negative queries, explicit explanation of why the question cannot be answered by the knowledge base."
    )

    # Backward compatibility properties
    @property
    def expected_document_titles(self) -> List[str]:
        return list({t.document_title for t in self.target_chunks})

    @property
    def expected_chunk_indices(self) -> List[int]:
        return [t.chunk_index for t in self.target_chunks]


class EvaluationDataset(BaseModel):
    name: str = "Apex Ops Customer Support RAG Evaluation Dataset"
    version: str = "1.1.0"
    description: str = "Curated evaluation benchmark with verified ground-truth chunk mappings covering returns, refunds, shipping, warranties, cancellations, and out-of-scope negative queries."
    queries: List[EvaluationQuery]


DEFAULT_EVALUATION_QUERIES: List[EvaluationQuery] = [
    # --------------------------------------------------------------------------------------------------
    # 1. RETURNS & ELIGIBILITY (Positive Queries)
    # --------------------------------------------------------------------------------------------------
    EvaluationQuery(
        id="eval-01",
        question="How many days do I have to return an item after delivery?",
        category="returns",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=0,
                section_title="1. Eligibility Window",
                rationale="Explicitly states that customers may request a return within 30 calendar days from the confirmed delivery date."
            )
        ],
        ground_truth_answer="Returns must be requested within 30 calendar days from the confirmed delivery date.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-02",
        question="What condition does my keyboard need to be in for a return to be accepted?",
        category="returns",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=0,
                section_title="1. Eligibility Window",
                rationale="Specifies that products must be returned in original packaging with all cables, manuals, and accessories, showing no cosmetic damage or tampering."
            )
        ],
        ground_truth_answer="Items must be in original packaging with all accessories, manuals, and cables, and show no signs of cosmetic damage or unauthorized tampering.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-03",
        question="Do you provide a free return shipping label if my product arrived defective or broken?",
        category="returns",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=2,
                section_title="3. Pre-paid Return Labels",
                rationale="States that for all defective items or orders received damaged, Apex Operations provides a complimentary pre-paid shipping return label."
            )
        ],
        ground_truth_answer="Yes, Apex Operations provides a complimentary pre-paid shipping return label for defective or damaged items.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-04",
        question="If I return an item simply because I changed my mind, do I have to pay for shipping?",
        category="returns",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=2,
                section_title="3. Pre-paid Return Labels",
                rationale="States that for voluntary returns (change of mind), a flat return shipping fee of $7.50 is deducted from the refund total."
            )
        ],
        ground_truth_answer="Yes, for voluntary change-of-mind returns, a flat return shipping fee of $7.50 is deducted from the refund.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-05",
        question="How do I initiate a return and get an RMA number approved?",
        category="returns",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=3,
                section_title="5. How to Initiate",
                rationale="Specifies contacting support with the Order Reference Number and photos if damaged, with staff approving an RMA within 24 hours."
            )
        ],
        ground_truth_answer="Contact support with your Order Reference Number and photos of damage; staff will approve an RMA within 24 hours.",
        is_negative=False
    ),

    # --------------------------------------------------------------------------------------------------
    # 2. REFUNDS & PROCESSING TIMELINES (Positive Queries)
    # --------------------------------------------------------------------------------------------------
    EvaluationQuery(
        id="eval-06",
        question="How long does it take to get my money refunded after the warehouse receives my return?",
        category="refunds",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=1,
                section_title="2. Refund Processing Time",
                rationale="States warehouse inspects returned items within 2 business days, and refunds are credited back to the original payment method within 3 to 5 business days."
            )
        ],
        ground_truth_answer="Inspection takes 2 business days after receipt, and refunds are credited back to the original payment method in 3 to 5 business days.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-07",
        question="Will my refund go back to my original credit card or do you issue store credit?",
        category="refunds",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=1,
                section_title="2. Refund Processing Time",
                rationale="Explicitly affirms that refunds are credited back to the original method of payment rather than store credit."
            )
        ],
        ground_truth_answer="Refunds are credited back to the original method of payment.",
        is_negative=False
    ),

    # --------------------------------------------------------------------------------------------------
    # 3. ORDER POLICIES & NON-RETURNABLE ITEMS (Positive Queries)
    # --------------------------------------------------------------------------------------------------
    EvaluationQuery(
        id="eval-08",
        question="Can I return custom-configured hardware or gift cards if I no longer need them?",
        category="order_policies",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=3,
                section_title="4. Non-Returnable Items",
                rationale="Defines custom-configured hardware, downloadable software licenses, and gift cards as final sale that cannot be returned or exchanged under any circumstances."
            )
        ],
        ground_truth_answer="No, custom-configured hardware and gift cards are final sale and non-returnable.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-09",
        question="What details must I provide to support when requesting an RMA?",
        category="order_policies",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=3,
                section_title="5. How to Initiate",
                rationale="States customers must contact support with their Order Reference Number (e.g. ORD-1001) and photos of the item if damaged."
            )
        ],
        ground_truth_answer="You must provide your Order Reference Number and photos of the item if damaged.",
        is_negative=False
    ),

    # --------------------------------------------------------------------------------------------------
    # 4. SHIPPING & DELIVERY (Positive Queries)
    # --------------------------------------------------------------------------------------------------
    EvaluationQuery(
        id="eval-10",
        question="How quickly do in-stock orders get processed and dispatched from your fulfillment center?",
        category="shipping",
        target_chunks=[
            TargetChunkReference(
                document_file="shipping_delivery_guidelines.txt",
                document_title="Shipping and Delivery Guidelines",
                chunk_index=0,
                section_title="1. Order Processing Time",
                rationale="Specifies that standard in-stock orders are processed and packaged within 24 to 48 business hours of receipt."
            )
        ],
        ground_truth_answer="In-stock orders are processed and packaged within 24 to 48 business hours of receipt.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-11",
        question="If I place an order on Saturday afternoon, when will it be dispatched?",
        category="shipping",
        target_chunks=[
            TargetChunkReference(
                document_file="shipping_delivery_guidelines.txt",
                document_title="Shipping and Delivery Guidelines",
                chunk_index=0,
                section_title="1. Order Processing Time",
                rationale="States that orders placed over weekends or statutory holidays will be dispatched on the next business day."
            )
        ],
        ground_truth_answer="Orders placed over weekends are dispatched on the next business day.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-12",
        question="What are your standard ground delivery timeframes and which carriers handle them?",
        category="shipping",
        target_chunks=[
            TargetChunkReference(
                document_file="shipping_delivery_guidelines.txt",
                document_title="Shipping and Delivery Guidelines",
                chunk_index=1,
                section_title="2. Shipping Methods and Delivery Estimates",
                rationale="Details Standard Ground Shipping as 3 to 5 business days handled via FedEx Ground or UPS Standard."
            )
        ],
        ground_truth_answer="Standard Ground Shipping takes 3 to 5 business days across continental regions via FedEx Ground or UPS Standard.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-13",
        question="Do you offer 1-2 day express priority shipping for urgent orders?",
        category="shipping",
        target_chunks=[
            TargetChunkReference(
                document_file="shipping_delivery_guidelines.txt",
                document_title="Shipping and Delivery Guidelines",
                chunk_index=1,
                section_title="2. Shipping Methods and Delivery Estimates",
                rationale="Details Express Priority Shipping as 1 to 2 business days handled via DHL Express or FedEx 2-Day."
            )
        ],
        ground_truth_answer="Yes, Express Priority Shipping delivers in 1 to 2 business days via DHL Express or FedEx 2-Day.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-14",
        question="When does the shipment tracking link become active after carrier pickup?",
        category="shipping",
        target_chunks=[
            TargetChunkReference(
                document_file="shipping_delivery_guidelines.txt",
                document_title="Shipping and Delivery Guidelines",
                chunk_index=2,
                section_title="3. Tracking Updates and In-Transit Delays",
                rationale="States tracking links become active within 12 hours of courier pickup."
            )
        ],
        ground_truth_answer="Tracking links become active within 12 hours of courier pickup.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-15",
        question="My parcel tracking status has been stuck without updates for 3 days. What is your policy?",
        category="shipping",
        target_chunks=[
            TargetChunkReference(
                document_file="shipping_delivery_guidelines.txt",
                document_title="Shipping and Delivery Guidelines",
                chunk_index=2,
                section_title="3. Tracking Updates and In-Transit Delays",
                rationale="States that if tracking does not update for more than 48 hours in transit, support initiates a formal carrier investigation."
            )
        ],
        ground_truth_answer="If tracking is stalled for over 48 hours, support initiates a formal carrier investigation.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-16",
        question="The carrier marked my order as delivered, but the parcel is missing from my doorstep.",
        category="shipping",
        target_chunks=[
            TargetChunkReference(
                document_file="shipping_delivery_guidelines.txt",
                document_title="Shipping and Delivery Guidelines",
                chunk_index=3,
                section_title="4. Damaged or Lost Shipments",
                rationale="Instructs customer to notify support within 5 business days if marked delivered but missing; team dispatches free replacement or full refund after carrier tracer."
            )
        ],
        ground_truth_answer="Notify support within 5 business days; Apex will dispatch a free replacement or full refund following carrier tracer verification.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-17",
        question="The shipping box arrived crushed with visible transit damage. How do I get a replacement?",
        category="shipping",
        target_chunks=[
            TargetChunkReference(
                document_file="shipping_delivery_guidelines.txt",
                document_title="Shipping and Delivery Guidelines",
                chunk_index=3,
                section_title="4. Damaged or Lost Shipments",
                rationale="Specifies that if parcel arrives with visible packaging damage, notify team within 5 business days for a free replacement or refund."
            )
        ],
        ground_truth_answer="Report visible transit damage within 5 business days to receive a free replacement or full refund.",
        is_negative=False
    ),

    # --------------------------------------------------------------------------------------------------
    # 5. WARRANTIES & HARDWARE SUPPORT (Positive Queries)
    # --------------------------------------------------------------------------------------------------
    EvaluationQuery(
        id="eval-18",
        question="What is the warranty period on Apex keyboards, headsets, and electronic accessories?",
        category="warranties",
        target_chunks=[
            TargetChunkReference(
                document_file="warranty_support_policy.txt",
                document_title="Hardware Warranty & Technical Support Policy",
                chunk_index=0,
                section_title="1. Limited Manufacturer Warranty",
                rationale="Specifies a 1-Year Limited Manufacturer Warranty covering internal component defects, firmware faults, and assembly failures."
            )
        ],
        ground_truth_answer="All electronic accessories and peripherals include a 1-Year Limited Manufacturer Warranty.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-19",
        question="Does your warranty cover liquid spills or water damage if I accidentally spill coffee?",
        category="warranties",
        target_chunks=[
            TargetChunkReference(
                document_file="warranty_support_policy.txt",
                document_title="Hardware Warranty & Technical Support Policy",
                chunk_index=1,
                section_title="2. What is Not Covered",
                rationale="Explicitly states that the warranty excludes normal wear and tear, water spillages, drops, and electrical surges."
            )
        ],
        ground_truth_answer="No, the warranty excludes water spillages, drops, normal wear and tear, and electrical surge damage.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-20",
        question="If my hardware unit is confirmed defective under warranty, do I have to pay for replacement shipping?",
        category="warranties",
        target_chunks=[
            TargetChunkReference(
                document_file="warranty_support_policy.txt",
                document_title="Hardware Warranty & Technical Support Policy",
                chunk_index=2,
                section_title="3. Rapid Replacement Guarantee",
                rationale="States support ships an expedited replacement with a prepaid return box, and the customer will not be charged for return shipping."
            )
        ],
        ground_truth_answer="No, Apex ships an expedited replacement unit with a prepaid box at no charge for return shipping.",
        is_negative=False
    ),
    EvaluationQuery(
        id="eval-21",
        question="What hours can I reach your technical operations support department?",
        category="warranties",
        target_chunks=[
            TargetChunkReference(
                document_file="warranty_support_policy.txt",
                document_title="Hardware Warranty & Technical Support Policy",
                chunk_index=2,
                section_title="4. Contacting Technical Support",
                rationale="States technical operations operate Monday through Friday from 8:00 AM to 8:00 PM EST, with urgent weekend triage for enterprise tiers."
            )
        ],
        ground_truth_answer="Technical support is available Monday through Friday from 8:00 AM to 8:00 PM EST.",
        is_negative=False
    ),

    # --------------------------------------------------------------------------------------------------
    # 6. CANCELLATIONS (Positive Queries)
    # --------------------------------------------------------------------------------------------------
    EvaluationQuery(
        id="eval-22",
        question="Can I cancel and refund an order for a downloadable software license key?",
        category="cancellations",
        target_chunks=[
            TargetChunkReference(
                document_file="return_refund_policy.txt",
                document_title="Customer Return and Refund Policy",
                chunk_index=3,
                section_title="4. Non-Returnable Items",
                rationale="Explicitly defines downloadable software licenses as final sale that cannot be returned, cancelled, or exchanged under any circumstances."
            )
        ],
        ground_truth_answer="No, downloadable software licenses are final sale and non-cancellable/non-refundable.",
        is_negative=False
    ),

    # --------------------------------------------------------------------------------------------------
    # 7. NEGATIVE / OUT-OF-SCOPE QUERIES (Expected NO Relevant Knowledge Base Chunk)
    # --------------------------------------------------------------------------------------------------
    EvaluationQuery(
        id="eval-23",
        question="What are your customs import duty rates and local VAT fees for international shipping to Germany?",
        category="negative_unsupported",
        target_chunks=[],
        ground_truth_answer="The knowledge base does not cover European customs tariffs, German VAT rates, or international duty collection procedures.",
        is_negative=True,
        negative_reasoning="The KB Shipping Policy only specifies domestic delivery 'across continental regions' via FedEx/UPS/DHL. Any retrieved chunk mentioning shipping methods is semantically related to freight, but completely irrelevant to German customs duties (False Positive)."
    ),
    EvaluationQuery(
        id="eval-24",
        question="Can I pick up my headset today at your physical retail store in Chicago?",
        category="negative_unsupported",
        target_chunks=[],
        ground_truth_answer="Apex Operations operates online fulfillment centers only; no retail stores or in-person customer pickup locations exist in the knowledge base.",
        is_negative=True,
        negative_reasoning="The KB contains zero references to retail store locations or in-person curbside pickup. Any chunk retrieved talking about warehousing is irrelevant to physical retail operations."
    ),
    EvaluationQuery(
        id="eval-25",
        question="Do you have an old keyboard trade-in or electronics recycling discount program?",
        category="negative_unsupported",
        target_chunks=[],
        ground_truth_answer="The knowledge base contains no trade-in program, device recycling rebate, or credit swap policy.",
        is_negative=True,
        negative_reasoning="The KB documents product warranties and return logistics, but has no device recycling or trade-in trade credit program."
    ),
    EvaluationQuery(
        id="eval-26",
        question="Will Apex price-match if Best Buy or Amazon has this chair on sale next week?",
        category="negative_unsupported",
        target_chunks=[],
        ground_truth_answer="The knowledge base does not contain any competitor price-matching or post-purchase price adjustment guarantee.",
        is_negative=True,
        negative_reasoning="The KB covers returns, shipping, and warranty defects, but has no competitor price-matching policy. A chunk retrieved mentioning chairs or voluntary return fees is topic-adjacent noise, not an answer."
    ),
    EvaluationQuery(
        id="eval-27",
        question="How do I change my shipping address or cancel my order 5 minutes after placing it using the self-service portal?",
        category="negative_unsupported",
        target_chunks=[],
        ground_truth_answer="The knowledge base documents warehouse processing times (24-48 hours), but does not support or document a 5-minute automated self-service cancellation or address alteration workflow.",
        is_negative=True,
        negative_reasoning="The KB Order Processing section mentions that orders are packaged in 24-48 hours, but does not provide an automated immediate cancellation or address change window. Retrieving processing time is related context, but does not answer how to cancel in a self-service portal."
    ),
    EvaluationQuery(
        id="eval-28",
        question="Can I pay for my order in 4 monthly installments using Klarna or Affirm?",
        category="negative_unsupported",
        target_chunks=[],
        ground_truth_answer="The knowledge base contains no installment financing, Buy Now Pay Later (BNPL), or third-party credit payment options.",
        is_negative=True,
        negative_reasoning="The KB Refund section mentions 'original method of payment', but the KB contains no financing or BNPL options."
    )
]


def get_default_evaluation_dataset() -> EvaluationDataset:
    """Returns the default curated evaluation dataset with verified ground-truth chunk references."""
    return EvaluationDataset(queries=DEFAULT_EVALUATION_QUERIES)
