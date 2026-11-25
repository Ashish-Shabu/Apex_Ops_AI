from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal, init_db
from backend.app.core.logging import logger
from backend.app.models.enquiry import Enquiry, EnquiryStatus, EnquiryCategory, EnquiryPriority
from backend.app.models.draft import ResponseDraft, DraftStatus
from backend.app.models.document import Document, DocumentChunk
from backend.app.models.order import Order, OrderItem
from backend.app.models.audit import AuditLog
from backend.app.services.document_parser import chunk_text
from backend.app.services.ai.embeddings import get_embeddings, get_active_embedding_config

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


SAMPLE_DOCUMENTS = [
    {
        "title": "Customer Return and Refund Policy",
        "file_name": "return_refund_policy.txt",
        "file_type": "txt",
        "content": """CUSTOMER RETURN AND REFUND POLICY - APEX OPERATIONS INC.

1. Eligibility Window
Customers may request a return within 30 calendar days from the confirmed delivery date. To be eligible for a refund, products must be returned in their original packaging, including all cables, manuals, and accessories, and show no signs of cosmetic damage or unauthorized tampering.

2. Refund Processing Time
Once our return logistics warehouse receives and inspects the item (typically 2 business days after receipt), we will process your refund. Refunds are credited back to the original method of payment within 3 to 5 business days, depending on your financial institution's processing schedule.

3. Pre-paid Return Labels
For all defective items or orders received in damaged condition, Apex Operations provides a complimentary pre-paid shipping return label. For voluntary returns (e.g. change of mind), a flat return shipping fee of $7.50 is deducted from the refund total.

4. Non-Returnable Items
Custom-configured hardware, downloadable software licenses, and gift cards are final sale and cannot be returned or exchanged under any circumstances.

5. How to Initiate
Contact our support team with your Order Reference Number (e.g. ORD-1001) and photos of the item if damaged. Our staff will approve a Return Merchandise Authorization (RMA) within 24 hours."""
    },
    {
        "title": "Shipping and Delivery Guidelines",
        "file_name": "shipping_delivery_guidelines.txt",
        "file_type": "txt",
        "content": """SHIPPING AND DELIVERY POLICY - APEX OPERATIONS INC.

1. Order Processing Time
All standard in-stock orders are processed and packaged within 24 to 48 business hours of receipt. Orders placed over weekends or statutory holidays will be dispatched on the next business day.

2. Shipping Methods and Delivery Estimates
- Standard Ground Shipping: 3 to 5 business days across continental regions. Handled via FedEx Ground or UPS Standard.
- Express Priority Shipping: 1 to 2 business days. Handled via DHL Express or FedEx 2-Day.
- All shipments include end-to-end tracking updates sent via email and SMS notification.

3. Tracking Updates and In-Transit Delays
Tracking links become active within 12 hours of courier pickup. If your tracking status does not update for more than 48 hours while in transit, or displays an exception notice, our support staff will initiate a formal investigation with the carrier.

4. Damaged or Lost Shipments
If your parcel arrives with visible packaging damage or if the courier marks it as delivered but you cannot locate it, notify our team within 5 business days. We will dispatch a free replacement or issue a full refund following our carrier tracer verification."""
    },
    {
        "title": "Hardware Warranty & Technical Support Policy",
        "file_name": "warranty_support_policy.txt",
        "file_type": "txt",
        "content": """HARDWARE WARRANTY AND SUPPORT GUIDELINES

1. Limited Manufacturer Warranty
All electronic accessories, keyboards, headsets, and computer peripherals sold by Apex Operations include a comprehensive 1-Year Limited Manufacturer Warranty covering internal component defects, firmware faults, and assembly failures.

2. What is Not Covered
The warranty excludes normal wear and tear, water spillages, drops, electrical surge damage from uncertified power supplies, and modifications made by unauthorized repair technicians.

3. Rapid Replacement Guarantee
If technical support confirms a hardware defect within the warranty period, we will ship an expedited replacement unit along with a prepaid box to return the malfunctioning unit. You will not be charged for return shipping.

4. Contacting Technical Support
Technical operations operate Monday through Friday from 8:00 AM to 8:00 PM EST. Urgent triage is available on weekends for enterprise account tiers."""
    }
]

SAMPLE_ORDERS = [
    {
        "order_number": "ORD-1001",
        "customer_name": "John Doe",
        "customer_email": "john.doe@example.com",
        "status": "delivered",
        "total_amount": 249.99,
        "currency": "USD",
        "tracking_number": "TRK-9821441",
        "carrier": "FedEx Ground",
        "shipping_address": "742 Evergreen Terrace, Springfield, OR 97477",
        "order_date": utc_now() - timedelta(days=5),
        "estimated_delivery": utc_now() - timedelta(days=2),
        "delivered_at": utc_now() - timedelta(days=2),
        "items": [
            {"sku": "CHAIR-ERG-01", "product_name": "Apex Ergonomic Mesh Desk Chair", "quantity": 1, "unit_price": 249.99}
        ]
    },
    {
        "order_number": "ORD-1002",
        "customer_name": "Alice Smith",
        "customer_email": "alice.smith@example.com",
        "status": "in_transit",
        "total_amount": 129.50,
        "currency": "USD",
        "tracking_number": "TRK-5519203",
        "carrier": "DHL Express",
        "shipping_address": "1200 Market Street, Suite 400, Philadelphia, PA 19107",
        "order_date": utc_now() - timedelta(days=2),
        "estimated_delivery": utc_now() + timedelta(days=1),
        "delivered_at": None,
        "items": [
            {"sku": "KB-MECH-W", "product_name": "Apex Pro Wireless Mechanical Keyboard", "quantity": 1, "unit_price": 129.50}
        ]
    },
    {
        "order_number": "ORD-1003",
        "customer_name": "Michael Brown",
        "customer_email": "michael.brown@example.com",
        "status": "processing",
        "total_amount": 199.00,
        "currency": "USD",
        "tracking_number": None,
        "carrier": "UPS Ground",
        "shipping_address": "456 Oak Avenue, Austin, TX 78701",
        "order_date": utc_now() - timedelta(hours=14),
        "estimated_delivery": utc_now() + timedelta(days=4),
        "delivered_at": None,
        "items": [
            {"sku": "HEADSET-NC-BLK", "product_name": "Apex QuietAudio ANC Wireless Headset", "quantity": 1, "unit_price": 199.00}
        ]
    },
    {
        "order_number": "ORD-1004",
        "customer_name": "Emily Davis",
        "customer_email": "emily.davis@example.com",
        "status": "refunded",
        "total_amount": 79.99,
        "currency": "USD",
        "tracking_number": "TRK-1102934",
        "carrier": "USPS Priority",
        "shipping_address": "88 Pine Street, Seattle, WA 98101",
        "order_date": utc_now() - timedelta(days=12),
        "estimated_delivery": utc_now() - timedelta(days=8),
        "delivered_at": utc_now() - timedelta(days=8),
        "items": [
            {"sku": "CAM-4K-PRO", "product_name": "Apex StreamView 4K Ultra Webcam", "quantity": 1, "unit_price": 79.99}
        ]
    }
]


def seed_database(db: Session = None):
    """Seed initial sample orders, documents, and enquiries."""
    close_db = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_db = True

    try:
        # Check if already seeded
        if db.query(Order).count() > 0:
            logger.info("Database already seeded with orders. Skipping initial seed.")
            return

        logger.info("Starting database seeding...")

        # 1. Seed Orders
        for o_data in SAMPLE_ORDERS:
            items_data = o_data.pop("items")
            order = Order(**o_data)
            db.add(order)
            db.flush()
            for it in items_data:
                item = OrderItem(order_id=order.id, **it)
                db.add(item)
        db.commit()
        logger.info("Seeded sample orders.")

        # 2. Seed Documents and Chunks with Embeddings
        active_config = get_active_embedding_config()
        for doc_info in SAMPLE_DOCUMENTS:
            content = doc_info["content"]
            doc = Document(
                title=doc_info["title"],
                file_name=doc_info["file_name"],
                file_type=doc_info["file_type"],
                file_size_bytes=len(content.encode("utf-8")),
                chunk_count=0,
                embedding_provider=active_config["provider"],
                embedding_model=active_config["model"],
                embedding_dimension=active_config["dimension"]
            )
            db.add(doc)
            db.flush()

            chunks_data = chunk_text(content, chunk_size=450, chunk_overlap=80)
            chunk_texts = [c["content"] for c in chunks_data]
            embeddings = get_embeddings(chunk_texts)

            for idx, c in enumerate(chunks_data):
                chunk_obj = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=c["chunk_index"],
                    content=c["content"],
                    embedding=embeddings[idx],
                    embedding_provider=active_config["provider"],
                    embedding_model=active_config["model"],
                    embedding_dimension=active_config["dimension"],
                    metadata_info=c["metadata_info"]
                )
                db.add(chunk_obj)

            doc.chunk_count = len(chunks_data)
        db.commit()
        logger.info("Seeded knowledge base documents with vector embeddings.")

        # 3. Seed Sample Enquiries
        # Enquiry 1: Delivery status check (awaiting approval)
        enq1 = Enquiry(
            customer_name="Alice Smith",
            customer_email="alice.smith@example.com",
            channel="email",
            subject="Where is my keyboard? Tracking update needed",
            message="Hi, I ordered the Apex Pro Wireless keyboard two days ago under order ORD-1002. Can you tell me when it will arrive? The tracking link doesn't show today's status.",
            category=EnquiryCategory.DELIVERY,
            status=EnquiryStatus.AWAITING_APPROVAL,
            priority=EnquiryPriority.MEDIUM,
            sentiment="frustrated",
            ai_summary="Customer Alice Smith is requesting delivery status and tracking update for order ORD-1002.",
            ai_confidence=0.96,
            order_number="ORD-1002"
        )
        db.add(enq1)
        db.flush()

        draft1 = ResponseDraft(
            enquiry_id=enq1.id,
            draft_body="""Dear Alice,

Thank you for reaching out regarding your order ORD-1002.

We checked your shipment with DHL Express:
• Current Status: IN TRANSIT
• Tracking Number: TRK-5519203
• Estimated Delivery: Tomorrow, by 7:00 PM
• Items: 1x Apex Pro Wireless Mechanical Keyboard

Per our Shipping Policy, carrier tracking updates refresh every 24 hours. Your parcel is on schedule and currently at the regional distribution facility.

Please let us know if we can assist with anything else!

Warm regards,
Apex Customer Support""",
            rationale="[DEMO MODE: Deterministic Operations Engine] Grounded in Shipping Policy (Chunk #1) and live order status from lookup_order tool for ORD-1002.",
            retrieved_sources=[
                {"document_title": "Shipping and Delivery Guidelines", "chunk_index": 1, "similarity_score": 0.88}
            ],
            tool_calls_used=[
                {"tool_name": "lookup_order", "arguments": {"order_number": "ORD-1002"}, "result": {"found": True, "status": "in_transit"}}
            ],
            status=DraftStatus.PENDING_REVIEW
        )
        db.add(draft1)

        log1 = AuditLog(
            enquiry_id=enq1.id,
            action="enquiry_created",
            actor="customer:alice.smith@example.com",
            details={"channel": "email"}
        )
        log2 = AuditLog(
            enquiry_id=enq1.id,
            action="draft_generated",
            actor="ai_assistant",
            details={"tools": ["lookup_order"], "status": "awaiting_approval"}
        )
        db.add_all([log1, log2])

        # Enquiry 2: Return & refund request (pending)
        enq2 = Enquiry(
            customer_name="John Doe",
            customer_email="john.doe@example.com",
            channel="web_chat",
            subject="Return request for ergonomic chair",
            message="Hello, I received the mesh chair under order ORD-1001 a couple days ago, but the seat depth does not fit my height. How do I return this for a full refund? Do you provide a return label?",
            category=EnquiryCategory.REFUND_RETURN,
            status=EnquiryStatus.PENDING,
            priority=EnquiryPriority.MEDIUM,
            sentiment="neutral",
            ai_summary="Customer John Doe wants to return the ergonomic chair from order ORD-1001 and requests a return label.",
            ai_confidence=0.98,
            order_number="ORD-1001"
        )
        db.add(enq2)
        db.flush()

        log3 = AuditLog(
            enquiry_id=enq2.id,
            action="enquiry_created",
            actor="customer:john.doe@example.com",
            details={"channel": "web_chat"}
        )
        db.add(log3)

        # Enquiry 3: Warranty policy question (resolved)
        enq3 = Enquiry(
            customer_name="David Wilson",
            customer_email="david.wilson@example.com",
            channel="email",
            subject="Headset warranty question after spillage",
            message="Hi team, does the manufacturer warranty cover accidental water spill on the headset microphone?",
            category=EnquiryCategory.COMPANY_POLICY,
            status=EnquiryStatus.RESOLVED,
            priority=EnquiryPriority.LOW,
            sentiment="neutral",
            ai_summary="Customer David Wilson is asking if warranty covers accidental liquid damage.",
            ai_confidence=0.92,
            order_number=None
        )
        db.add(enq3)
        db.flush()

        draft3 = ResponseDraft(
            enquiry_id=enq3.id,
            draft_body="""Dear David,

Thank you for contacting technical support.

According to our Hardware Warranty Guidelines, accidental liquid damage and water spillages are unfortunately excluded from the 1-Year Limited Manufacturer Warranty.

However, we do offer out-of-warranty replacement parts and repair assistance at a discounted customer rate. If you would like to proceed with a replacement microphone module, please let us know!

Warm regards,
Apex Operations Support""",
            rationale="Grounded in Hardware Warranty & Technical Support Policy (Chunk #1). Accidental damage exclusion confirmed.",
            status=DraftStatus.APPROVED,
            reviewed_by="Support Lead Marcus",
            reviewed_at=utc_now() - timedelta(hours=3),
            review_feedback="Approved and sent."
        )
        db.add(draft3)

        log4 = AuditLog(
            enquiry_id=enq3.id,
            action="draft_approved",
            actor="staff:Marcus",
            details={"status": "resolved"}
        )
        db.add(log4)

        db.commit()
        logger.info("Sample database seeding completed successfully.")

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    seed_database()
