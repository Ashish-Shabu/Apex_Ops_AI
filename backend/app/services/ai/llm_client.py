import copy
import json
import re
from typing import Dict, Any, List, Optional
import httpx
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.services.ai.tools import AVAILABLE_TOOLS_DEFINITIONS, execute_tool
from backend.app.services.ai.order_validator import validate_order_products, OrderValidationResult
from backend.app.services.ai.text_utils import (
    format_policy_context,
    deduplicate_repetitive_words,
    sanitize_draft_response,
    enforce_mismatch_privacy
)
from sqlalchemy.orm import Session


class LLMClient:
    """
    Unified LLM Client.
    Supports:
    1. Google Gemini via official google-genai SDK (Default provider)
    2. OpenAI API (Optional secondary provider)
    3. Deterministic Demo Mode Engine (Zero-dependency fallback)
    """

    def __init__(self):
        self.model = settings.LLM_MODEL

    @property
    def provider(self) -> str:
        return settings.active_provider

    @property
    def is_demo_mode(self) -> bool:
        return settings.is_demo_mode

    def classify_and_summarize(self, customer_name: str, subject: str, message: str) -> Dict[str, Any]:
        """
        Classifies the enquiry category, priority, sentiment, and extracts summary & order numbers.
        Dispatches to active provider with automatic fallback.
        """
        active_provider = self.provider

        if active_provider == "gemini":
            try:
                return self._classify_gemini(customer_name, subject, message)
            except Exception as e:
                logger.error(f"Gemini classification failed: {e}. Falling back to deterministic demo engine.")

        elif active_provider == "openai":
            try:
                return self._classify_openai(customer_name, subject, message)
            except Exception as e:
                logger.error(f"OpenAI classification failed: {e}. Falling back to deterministic demo engine.")

        return self._classify_deterministic_demo(customer_name, subject, message)

    def generate_response_draft(
        self,
        enquiry_data: Dict[str, Any],
        retrieved_chunks: List[Dict[str, Any]],
        has_sufficient_knowledge: bool,
        db: Session,
        staff_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates context-aware response draft using enquiry, retrieved knowledge,
        and controlled backend tool execution (e.g. order lookup).
        Dispatches to active provider with automatic fallback.
        """
        active_provider = self.provider

        if active_provider == "gemini":
            try:
                return self._generate_draft_gemini(
                    enquiry_data, retrieved_chunks, has_sufficient_knowledge, db, staff_notes
                )
            except Exception as e:
                logger.error(f"Gemini draft generation failed: {e}. Falling back to deterministic demo engine.")

        elif active_provider == "openai":
            try:
                return self._generate_draft_openai(
                    enquiry_data, retrieved_chunks, has_sufficient_knowledge, db, staff_notes
                )
            except Exception as e:
                logger.error(f"OpenAI draft generation failed: {e}. Falling back to deterministic demo engine.")

        return self._generate_draft_deterministic_demo(
            enquiry_data, retrieved_chunks, has_sufficient_knowledge, db, staff_notes
        )

    # -------------------------------------------------------------------------
    # Google Gemini Integration (Official google-genai SDK)
    # -------------------------------------------------------------------------
    def _classify_gemini(self, customer_name: str, subject: str, message: str) -> Dict[str, Any]:
        """Classification & summarization using Google Gemini with structured JSON output."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        system_instruction = (
            "You are an AI customer support triage specialist. Analyze the incoming customer message and return "
            "a valid JSON object with the following keys:\n"
            "- category: one of ['order_status', 'delivery', 'refund_return', 'company_policy', 'general_support']\n"
            "- priority: one of ['low', 'medium', 'high', 'urgent']\n"
            "- sentiment: one of ['positive', 'neutral', 'frustrated', 'angry']\n"
            "- summary: a concise 1-2 sentence summary of what the customer is asking\n"
            "- order_number_detected: extracted order reference number (e.g. ORD-1001) or null if none mentioned\n"
            "- key_entities: array of strings of key products, dates, or issues\n"
            "- confidence: float between 0.0 and 1.0\n"
            "Return ONLY the JSON object."
        )

        user_content = f"Customer Name: {customer_name}\nSubject: {subject}\nMessage:\n{message}"

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.1
        )

        response = client.models.generate_content(
            model=settings.LLM_MODEL,
            contents=user_content,
            config=config
        )

        raw_text = response.text or "{}"
        result = json.loads(raw_text)
        result["is_demo_mode"] = False
        result["provider"] = "gemini"
        return result

    def _generate_draft_gemini(
        self,
        enquiry_data: Dict[str, Any],
        retrieved_chunks: List[Dict[str, Any]],
        has_sufficient_knowledge: bool,
        db: Session,
        staff_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Context-aware response draft generation with Gemini function/tool calling."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        tools_executed = []

        sources_text = ""
        if retrieved_chunks:
            sources_text = "\n\n".join([
                f"[Document: {c['document_title']} (Chunk #{c['chunk_index']})]\n{c['content']}"
                for c in retrieved_chunks
            ])
        else:
            sources_text = "No relevant knowledge base documents found."

        system_instruction = (
            "You are an AI customer operations assistant helping human staff draft professional, accurate customer replies.\n"
            "Guidelines:\n"
            "1. Ground your response in the provided Company Knowledge Base chunks and order data.\n"
            "2. If an order number is mentioned or relevant, invoke the lookup_order tool to obtain factual order status.\n"
            "3. If knowledge base or order information is insufficient or unavailable, explicitly state what is missing and recommend human staff verify before sending.\n"
            "4. Maintain a warm, polite, and reassuring tone.\n"
            "5. Quality, Grammar & Precision:\n"
            "   - Ensure all sentences are complete, grammatical, and professional.\n"
            "   - Strictly avoid repetitive, redundant, or duplicated wording (e.g. never say 'pre-paid prepaid', 'free complimentary', or repeat phrases).\n"
            "   - When citing or quoting company policy, preserve complete relevant policy context without abrupt or mid-sentence truncation.\n"
            "   - Do not invent policy terms or alter actual company policy rules.\n"
            "6. After finalizing the draft, return a JSON object with keys: 'draft_body' (the customer-facing message) and 'rationale' (internal explanation of facts/sources used)."
        )

        user_content = (
            f"CUSTOMER ENQUIRY:\n"
            f"Customer Name: {enquiry_data.get('customer_name')}\n"
            f"Customer Email: {enquiry_data.get('customer_email')}\n"
            f"Subject: {enquiry_data.get('subject')}\n"
            f"Category: {enquiry_data.get('category')}\n"
            f"Order Reference: {enquiry_data.get('order_number') or 'None specified'}\n"
            f"Message: {enquiry_data.get('message')}\n\n"
            f"RETRIEVED KNOWLEDGE BASE CONTEXT:\n{sources_text}\n\n"
            f"STAFF NOTES: {staff_notes or 'None'}\n"
        )

        # Build Gemini Tool declarations
        gemini_tools = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="lookup_order",
                    description="Look up complete order details (status, tracking, items, address, delivery date) using an order number (e.g. ORD-1001).",
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "order_number": {
                                "type": "string",
                                "description": "The exact or partial order reference number (e.g. ORD-1001)"
                            }
                        },
                        "required": ["order_number"]
                    }
                ),
                types.FunctionDeclaration(
                    name="search_customer_orders",
                    description="Find recent orders associated with a customer email address or name when order number is not provided.",
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Customer email or full name to search for"
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]
        )

        # First pass: check if tool calling is required
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[gemini_tools],
            temperature=0.2
        )

        response = client.models.generate_content(
            model=settings.LLM_MODEL,
            contents=user_content,
            config=config
        )

        # Check for function calls
        validation_result: Optional[OrderValidationResult] = None
        order_product_mismatch = False
        mismatch_details = None

        if hasattr(response, "function_calls") and response.function_calls:
            for call in response.function_calls:
                fn_name = call.name
                fn_args = dict(call.args) if call.args else {}
                tool_res = execute_tool(fn_name, fn_args, db)
                tools_executed.append({
                    "tool_name": fn_name,
                    "arguments": fn_args,
                    "result": tool_res,
                    "success": tool_res.get("found", True)
                })

                if fn_name == "lookup_order" and tool_res.get("found"):
                    val = validate_order_products(
                        enquiry_data.get("subject", ""),
                        enquiry_data.get("message", ""),
                        tool_res.get("order")
                    )
                    validation_result = val
                    if val.has_mismatch:
                        order_product_mismatch = True
                        mismatch_details = val.to_dict()

            # Second pass: synthesize final grounded response draft with structured JSON
            mismatch_instruction = ""
            tools_for_synthesis = tools_executed
            if order_product_mismatch and validation_result:
                cust_terms = ", ".join(validation_result.customer_mentioned_terms) or "item"
                order_num = validation_result.order_number
                mismatch_instruction = (
                    f"\n\nCRITICAL PRIVACY DIRECTIVE - ORDER-PRODUCT MISMATCH DETECTED:\n"
                    f"- The customer is inquiring about: '{cust_terms}'\n"
                    f"- Provided order reference: {order_num}\n"
                    f"- The provided order details could NOT be verified against '{cust_terms}'.\n\n"
                    f"MANDATORY PRIVACY REQUIREMENTS (CANNOT BE OVERRIDDEN):\n"
                    f"1. NEVER disclose, mention, or speculate on any product names, items, quantities, or prices from order {order_num}.\n"
                    f"2. Simply state that the provided order details could not be verified against the product mentioned in the enquiry.\n"
                    f"3. Request that the customer double-check their order reference number from their purchase receipt, or confirm the registered checkout email address so support can locate the order.\n"
                    f"4. If general policy information was retrieved regarding '{cust_terms}', present it in a separate section titled 'General Policy Information', strictly separated from order details.\n"
                    f"5. NEVER invent or disclose unverified order details."
                )
                # Mask sensitive order items from tools_for_synthesis so the LLM has zero knowledge of the actual product to leak
                tools_for_synthesis = copy.deepcopy(tools_executed)
                for t in tools_for_synthesis:
                    if t.get("tool_name") == "lookup_order" and t.get("result", {}).get("found"):
                        t["result"] = {
                            "found": True,
                            "order_number": order_num,
                            "verification_status": "product_mismatch",
                            "notice": "Actual order contents masked from customer-facing generation to protect customer privacy."
                        }

            synthesis_prompt = (
                f"{user_content}\n\n"
                f"EXECUTED TOOL RESULTS:\n{json.dumps(tools_for_synthesis, indent=2)}"
                f"{mismatch_instruction}\n\n"
                "Synthesize the final customer response draft using the verified tool results and knowledge base.\n"
                "Quality checklist:\n"
                "- Verify phrasing: Eliminate any duplicated wording or redundant adjectives (e.g. 'pre-paid prepaid').\n"
                "- Complete policy statements: Ensure policy statements and excerpts form complete, coherent sentences without abrupt truncation.\n"
                "- Factual accuracy: Strictly separate verified order details from general policy information.\n"
                "Output a JSON object with keys 'draft_body' and 'rationale'."
            )

            synth_config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.2,
                max_output_tokens=2048
            )

            synth_resp = client.models.generate_content(
                model=settings.LLM_MODEL,
                contents=synthesis_prompt,
                config=synth_config
            )

            try:
                parsed = json.loads(synth_resp.text or "{}")
                draft_body = parsed.get("draft_body", synth_resp.text)
                rationale = parsed.get("rationale", "Grounded in retrieved sources and live order lookup via Gemini tools.")
            except Exception:
                draft_body = synth_resp.text or ""
                rationale = "Generated by Google Gemini."

            # Sanitize response to guarantee no duplicate phrasing or broken endings
            draft_body = sanitize_draft_response(draft_body)

            # Python-side validation guardrail: Enforce privacy and ensure sensitive product is never leaked
            if order_product_mismatch and validation_result:
                draft_body = enforce_mismatch_privacy(draft_body, validation_result)
                cust_terms = ", ".join(validation_result.customer_mentioned_terms) or "item"
                actual_prods = ", ".join(validation_result.order_actual_products)
                rationale = (
                    f"[INTERNAL STAFF WARNING: Order-Product Mismatch] Customer inquired about '{cust_terms}', "
                    f"but order {validation_result.order_number} is registered for '{actual_prods}'. "
                    f"Customer-facing response protected to avoid disclosing actual order contents. | {rationale}"
                )

            return {
                "draft_body": draft_body,
                "rationale": rationale,
                "sources_used": retrieved_chunks,
                "tools_executed": tools_executed,
                "order_product_mismatch": order_product_mismatch,
                "mismatch_details": mismatch_details,
                "is_demo_mode": False,
                "provider": "gemini"
            }
        else:
            # No tool called, parse direct response
            raw_text = response.text or ""
            try:
                parsed = json.loads(raw_text)
                draft_body = parsed.get("draft_body", raw_text)
                rationale = parsed.get("rationale", "Grounded in retrieved knowledge base chunks.")
            except Exception:
                draft_body = raw_text
                rationale = "Direct response draft generated by Google Gemini."

            draft_body = sanitize_draft_response(draft_body)

            return {
                "draft_body": draft_body,
                "rationale": rationale,
                "sources_used": retrieved_chunks,
                "tools_executed": tools_executed,
                "is_demo_mode": False,
                "provider": "gemini"
            }

    # -------------------------------------------------------------------------
    # OpenAI API Integrations (Optional Secondary Provider)
    # -------------------------------------------------------------------------
    def _classify_openai(self, customer_name: str, subject: str, message: str) -> Dict[str, Any]:
        system_prompt = (
            "You are an AI customer support triage specialist. Analyze the incoming customer message and return "
            "a valid JSON object with the following keys:\n"
            "- category: one of ['order_status', 'delivery', 'refund_return', 'company_policy', 'general_support']\n"
            "- priority: one of ['low', 'medium', 'high', 'urgent']\n"
            "- sentiment: one of ['positive', 'neutral', 'frustrated', 'angry']\n"
            "- summary: a concise 1-2 sentence summary of what the customer is asking\n"
            "- order_number_detected: extracted order reference number (e.g. ORD-1001) or null if none mentioned\n"
            "- key_entities: array of strings of key products, dates, or issues\n"
            "- confidence: float between 0.0 and 1.0\n"
            "Return ONLY the JSON object, nothing else."
        )

        user_content = f"Customer Name: {customer_name}\nSubject: {subject}\nMessage:\n{message}"

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            result["is_demo_mode"] = False
            result["provider"] = "openai"
            return result

    def _generate_draft_openai(
        self,
        enquiry_data: Dict[str, Any],
        retrieved_chunks: List[Dict[str, Any]],
        has_sufficient_knowledge: bool,
        db: Session,
        staff_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tool-calling chat completion with OpenAI."""
        tools_executed = []
        
        sources_text = ""
        if retrieved_chunks:
            sources_text = "\n\n".join([
                f"[Document: {c['document_title']} (Chunk #{c['chunk_index']})]\n{c['content']}"
                for c in retrieved_chunks
            ])
        else:
            sources_text = "No relevant knowledge base documents found."

        system_prompt = (
            "You are an AI customer operations assistant helping human staff draft professional, accurate customer replies.\n"
            "Guidelines:\n"
            "1. Ground your response in the provided Company Knowledge Base chunks and order data.\n"
            "2. If an order number is mentioned or relevant, call the 'lookup_order' tool to obtain factual order status.\n"
            "3. If knowledge base or order information is insufficient or unavailable, explicitly state what is missing and recommend human staff verify before sending.\n"
            "4. Maintain a warm, polite, and reassuring tone.\n"
            "5. Quality & Precision:\n"
            "   - Ensure all sentences are complete, grammatical, and professional.\n"
            "   - Strictly avoid repetitive, redundant, or duplicated wording (e.g. never say 'pre-paid prepaid', 'free complimentary', or repeat phrases).\n"
            "   - When citing or quoting company policy, preserve complete relevant policy context without abrupt or mid-sentence truncation.\n"
            "   - Do not invent policy terms or alter actual company policy rules.\n"
            "6. After finalizing the draft, output a JSON object with: 'draft_body' (the customer-facing message) and 'rationale' (internal explanation of facts/sources used)."
        )

        user_content = (
            f"CUSTOMER ENQUIRY:\n"
            f"Customer Name: {enquiry_data.get('customer_name')}\n"
            f"Customer Email: {enquiry_data.get('customer_email')}\n"
            f"Subject: {enquiry_data.get('subject')}\n"
            f"Category: {enquiry_data.get('category')}\n"
            f"Order Reference: {enquiry_data.get('order_number') or 'None specified'}\n"
            f"Message: {enquiry_data.get('message')}\n\n"
            f"RETRIEVED KNOWLEDGE BASE CONTEXT:\n{sources_text}\n\n"
            f"STAFF NOTES: {staff_notes or 'None'}\n"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

        with httpx.Client(timeout=45.0) as client:
            payload = {
                "model": settings.LLM_MODEL,
                "messages": messages,
                "tools": AVAILABLE_TOOLS_DEFINITIONS,
                "tool_choice": "auto",
                "temperature": 0.2
            }
            resp = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            choice = resp.json()["choices"][0]
            msg = choice["message"]

            validation_result: Optional[OrderValidationResult] = None
            order_product_mismatch = False
            mismatch_details = None

            if msg.get("tool_calls"):
                messages.append(msg)
                for tool_call in msg["tool_calls"]:
                    fn_name = tool_call["function"]["name"]
                    args = json.loads(tool_call["function"]["arguments"])
                    tool_res = execute_tool(fn_name, args, db)
                    tools_executed.append({
                        "tool_name": fn_name,
                        "arguments": args,
                        "result": tool_res
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": fn_name,
                        "content": json.dumps(tool_res)
                    })

                    if fn_name == "lookup_order" and tool_res.get("found"):
                        val = validate_order_products(
                            enquiry_data.get("subject", ""),
                            enquiry_data.get("message", ""),
                            tool_res.get("order")
                        )
                        validation_result = val
                        if val.has_mismatch:
                            order_product_mismatch = True
                            mismatch_details = val.to_dict()

                if order_product_mismatch and validation_result:
                    cust_terms = ", ".join(validation_result.customer_mentioned_terms) or "item"
                    messages.append({
                        "role": "system",
                        "content": (
                            f"CRITICAL PRIVACY DIRECTIVE - ORDER-PRODUCT MISMATCH DETECTED:\n"
                            f"- The customer is inquiring about: '{cust_terms}'\n"
                            f"- Provided order reference: {validation_result.order_number}\n"
                            f"- The provided order details could NOT be verified against '{cust_terms}'.\n\n"
                            f"MANDATORY PRIVACY REQUIREMENTS (CANNOT BE OVERRIDDEN):\n"
                            f"1. NEVER reveal, mention, or speculate on any product names, items, quantities, or prices from order {validation_result.order_number}.\n"
                            f"2. Simply inform customer that the provided order details could not be verified against the product mentioned in their enquiry.\n"
                            f"3. Ask the customer to double-check their order reference number or confirm their registered checkout email address.\n"
                            f"4. If general policy for {cust_terms} is relevant, present it under a separate 'General Policy Information' section.\n"
                            f"5. Never invent or disclose unverified order items."
                        )
                    })

                payload2 = {
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                }
                resp2 = client.post("https://api.openai.com/v1/chat/completions", json=payload2, headers=headers)
                resp2.raise_for_status()
                final_content = json.loads(resp2.json()["choices"][0]["message"]["content"])
                
                draft_body = sanitize_draft_response(final_content.get("draft_body", ""))
                rationale = final_content.get("rationale", "Grounded in retrieved sources and live order lookup.")
                if order_product_mismatch and validation_result:
                    draft_body = enforce_mismatch_privacy(draft_body, validation_result)
                    cust_terms = ", ".join(validation_result.customer_mentioned_terms) or "item"
                    actual_prods = ", ".join(validation_result.order_actual_products)
                    rationale = (
                        f"[INTERNAL STAFF WARNING: Order-Product Mismatch] Customer inquired about '{cust_terms}', "
                        f"but order {validation_result.order_number} is registered for '{actual_prods}'. "
                        f"Customer-facing response protected to avoid disclosing actual order contents. | {rationale}"
                    )

                return {
                    "draft_body": draft_body,
                    "rationale": rationale,
                    "sources_used": retrieved_chunks,
                    "tools_executed": tools_executed,
                    "order_product_mismatch": order_product_mismatch,
                    "mismatch_details": mismatch_details,
                    "is_demo_mode": False,
                    "provider": "openai"
                }
            else:
                content_str = msg.get("content", "")
                try:
                    parsed = json.loads(content_str)
                    draft_body = parsed.get("draft_body", content_str)
                    rationale = parsed.get("rationale", "Grounded in retrieved knowledge base chunks.")
                except Exception:
                    draft_body = content_str
                    rationale = "Direct response draft."

                draft_body = sanitize_draft_response(draft_body)

                return {
                    "draft_body": draft_body,
                    "rationale": rationale,
                    "sources_used": retrieved_chunks,
                    "tools_executed": tools_executed,
                    "is_demo_mode": False,
                    "provider": "openai"
                }

    # -------------------------------------------------------------------------
    # Deterministic Demo Mode Engine (Zero-dependency Fallback)
    # -------------------------------------------------------------------------
    def _classify_deterministic_demo(self, customer_name: str, subject: str, message: str) -> Dict[str, Any]:
        """Accurate rule-based deterministic classifier for demo mode without external API keys."""
        combined = f"{subject} {message}".lower()

        order_match = re.search(r"\b(ord[-_]?\d{3,6})\b", combined, re.IGNORECASE)
        order_num = order_match.group(1).upper() if order_match else None
        if not order_num:
            digit_match = re.search(r"#\s*(\d{4,6})\b", combined)
            if digit_match:
                order_num = f"ORD-{digit_match.group(1)}"

        if any(w in combined for w in ["refund", "return", "money back", "exchange", "faulty", "damaged"]):
            category = "refund_return"
        elif any(w in combined for w in ["delivery", "tracking", "shipped", "carrier", "transit", "arrive", "where is my"]):
            category = "delivery"
        elif any(w in combined for w in ["order", "purchase", "cancel", "status", "bought", "receipt"]):
            category = "order_status"
        elif any(w in combined for w in ["policy", "warranty", "terms", "hours", "headquarters", "privacy"]):
            category = "company_policy"
        else:
            category = "general_support"

        if any(w in combined for w in ["furious", "unacceptable", "terrible", "lawyer", "scam", "disaster"]):
            sentiment = "angry"
            priority = "urgent"
        elif any(w in combined for w in ["frustrated", "disappointed", "late", "still waiting", "wrong", "annoyed"]):
            sentiment = "frustrated"
            priority = "high"
        elif any(w in combined for w in ["thank", "great", "love", "appreciate"]):
            sentiment = "positive"
            priority = "low"
        else:
            sentiment = "neutral"
            priority = "medium"

        sentences = [s.strip() for s in re.split(r"[.!?\n]", message) if len(s.strip()) > 8]
        first_sentence = sentences[0] if sentences else subject
        clean_first = format_policy_context(first_sentence, max_chars=120)
        summary = f"Customer {customer_name} is enquiring about {category.replace('_', ' ')}: \"{clean_first}\""

        return {
            "category": category,
            "priority": priority,
            "sentiment": sentiment,
            "summary": summary,
            "order_number_detected": order_num,
            "key_entities": [w for w in ["refund", "damaged item", "tracking", "order"] if w in combined],
            "confidence": 0.94,
            "is_demo_mode": True,
            "provider": "demo",
            "engine": "Deterministic Operations Engine (Demo Mode)"
        }

    def _generate_draft_deterministic_demo(
        self,
        enquiry_data: Dict[str, Any],
        retrieved_chunks: List[Dict[str, Any]],
        has_sufficient_knowledge: bool,
        db: Session,
        staff_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Deterministic draft generator with simulated tool calling and document grounding."""
        tools_executed = []
        customer_name = enquiry_data.get("customer_name", "Customer")
        subject = enquiry_data.get("subject", "")
        message = enquiry_data.get("message", "")
        category = enquiry_data.get("category", "general_support")
        order_num = enquiry_data.get("order_number")

        if not order_num:
            m = re.search(r"\b(ord[-_]?\d{3,6})\b", message, re.IGNORECASE)
            if m:
                order_num = m.group(1).upper()

        order_details = None
        if order_num:
            tool_res = execute_tool("lookup_order", {"order_number": order_num}, db)
            tools_executed.append({
                "tool_name": "lookup_order",
                "arguments": {"order_number": order_num},
                "result": tool_res,
                "success": tool_res.get("found", False)
            })
            if tool_res.get("found"):
                order_details = tool_res["order"]
        elif category in ["order_status", "delivery", "refund_return"]:
            cust_email = enquiry_data.get("customer_email")
            if cust_email:
                tool_res = execute_tool("search_customer_orders", {"query": cust_email}, db)
                tools_executed.append({
                    "tool_name": "search_customer_orders",
                    "arguments": {"query": cust_email},
                    "result": tool_res,
                    "success": tool_res.get("count", 0) > 0
                })
                if tool_res.get("count", 0) > 0:
                    first_order_num = tool_res["orders"][0]["order_number"]
                    full_res = execute_tool("lookup_order", {"order_number": first_order_num}, db)
                    if full_res.get("found"):
                        order_details = full_res["order"]

        warning = None
        if not has_sufficient_knowledge and not order_details:
            warning = "Notice: Neither relevant knowledge base documents nor order records were found. Draft contains placeholder guidance for human agent verification."

        body_lines = [
            f"Dear {customer_name},",
            "",
            f"Thank you for contacting our customer support team regarding: \"{subject}\".",
            ""
        ]

        rationale_items = []
        validation_result: Optional[OrderValidationResult] = None
        order_product_mismatch = False
        mismatch_details = None

        if order_details:
            val = validate_order_products(subject, message, order_details)
            validation_result = val
            if val.has_mismatch:
                order_product_mismatch = True
                mismatch_details = val.to_dict()

        if order_details and order_product_mismatch and validation_result:
            order_num = validation_result.order_number

            body_lines.append(f"Important Notice Regarding Order {order_num}:")
            body_lines.append("The provided order details could not be verified against the product mentioned in your enquiry.")
            body_lines.append("For your security and privacy, could you please double-check your order number from your purchase receipt, or confirm the registered checkout email address so our support team can verify and locate your order?")
            body_lines.append("")

            # Requirement 4: Preserve general policy information when relevant, but clearly separate it from verified order information
            if retrieved_chunks:
                body_lines.append("General Policy Information:")
                top_chunk = retrieved_chunks[0]
                body_lines.append(f"• Per our {top_chunk['document_title']}:")
                formatted_policy = format_policy_context(top_chunk["content"])
                for p_line in formatted_policy.split("\n"):
                    if p_line.strip():
                        body_lines.append(f"  {p_line.strip()}")
                body_lines.append("")
                rationale_items.append(f"Separated general policy information from {top_chunk['document_title']}.")

            cust_term = ", ".join(validation_result.customer_mentioned_terms) or "item"
            order_items_str = ", ".join(validation_result.order_actual_products)
            rationale_items.append(
                f"[INTERNAL STAFF WARNING: Order-Product Mismatch] Customer mentioned '{cust_term}', but order {order_num} contains '{order_items_str}'. Customer-facing response protected to avoid disclosing mismatched order contents."
            )
        elif order_details:
            order_status = order_details['status'].upper()
            tracking = order_details.get('tracking_number') or 'Pending carrier assignment'
            carrier = order_details.get('carrier') or 'Standard Shipping'
            delivery_date = order_details.get('estimated_delivery') or 'in 2-3 business days'
            items_str = ", ".join([f"{i['quantity']}x {i['product_name']}" for i in order_details.get('items', [])])

            body_lines.append(f"We have located your order {order_details['order_number']}:")
            body_lines.append(f"• Current Status: {order_status}")
            body_lines.append(f"• Items: {items_str}")
            body_lines.append(f"• Carrier & Tracking: {carrier} ({tracking})")
            body_lines.append(f"• Estimated Delivery: {delivery_date}")
            body_lines.append("")

            rationale_items.append(f"Incorporated live order details for {order_details['order_number']} via lookup_order tool.")
        elif order_num and not order_details:
            body_lines.append(f"We investigated order number '{order_num}', but could not find a matching record in our active orders database.")
            body_lines.append("Could you please double-check the order number from your purchase receipt, or confirm the email address used during checkout?")
            body_lines.append("")
            rationale_items.append(f"lookup_order tool called for '{order_num}' but returned not found.")

        # If not already handled in mismatch block
        if retrieved_chunks and not (order_details and order_product_mismatch):
            top_chunk = retrieved_chunks[0]
            rationale_items.append(f"Grounded response in policy document '{top_chunk['document_title']}' (Chunk #{top_chunk['chunk_index']}).")
            
            if category == "refund_return":
                body_lines.append("Per our official Return Policy:")
                body_lines.append("• Items can be returned within 30 days of delivery in their original packaging.")
                body_lines.append("• Once received and inspected, refunds are credited back to your original payment method within 3-5 business days.")
                body_lines.append("• We will provide a pre-paid return shipping label upon confirmation.")
                body_lines.append("")
            elif category == "delivery":
                body_lines.append("Per our Shipping & Delivery Policy:")
                body_lines.append("• Standard delivery takes 3 to 5 business days, with tracking updates refreshed every 24 hours.")
                body_lines.append("• If a parcel does not show progress for more than 48 hours, our team initiates a priority carrier tracer.")
                body_lines.append("")
            elif category == "company_policy":
                body_lines.append("Regarding our company policy:")
                formatted_policy = format_policy_context(top_chunk["content"])
                for p_line in formatted_policy.split("\n"):
                    if p_line.strip():
                        body_lines.append(f"• {p_line.strip()}")
                body_lines.append("")
            else:
                body_lines.append("According to our verified guidelines:")
                formatted_policy = format_policy_context(top_chunk["content"])
                for p_line in formatted_policy.split("\n"):
                    if p_line.strip():
                        body_lines.append(f"• {p_line.strip()}")
                body_lines.append("")
        elif not retrieved_chunks and not order_details:
            body_lines.append("Our knowledge base does not currently contain a specific policy covering this query.")
            body_lines.append("Our operations specialist is reviewing your file and will provide tailored assistance shortly.")
            body_lines.append("")
            rationale_items.append("No relevant chunks retrieved from knowledge base; flagged for manual review.")

        if staff_notes:
            body_lines.append(f"Staff update: {staff_notes}")
            body_lines.append("")
            rationale_items.append("Appended internal staff guidance note.")

        body_lines.append("Please feel free to reply directly to this message if you have any additional questions.")
        body_lines.append("")
        body_lines.append("Warm regards,")
        body_lines.append("Customer Operations Team")

        draft_text = sanitize_draft_response("\n".join(body_lines))
        if order_product_mismatch and validation_result:
            draft_text = enforce_mismatch_privacy(draft_text, validation_result)
        rationale_text = " | ".join(rationale_items) if rationale_items else "Draft generated based on enquiry subject and category."

        return {
            "draft_body": draft_text,
            "rationale": f"[DEMO MODE: Deterministic Operations Engine] {rationale_text}",
            "sources_used": retrieved_chunks,
            "tools_executed": tools_executed,
            "order_product_mismatch": order_product_mismatch,
            "mismatch_details": mismatch_details,
            "is_demo_mode": True,
            "provider": "demo",
            "warning": warning
        }


llm_client = LLMClient()
