# AI Operations Assistant (Apex Ops AI)

An enterprise-ready, functional MVP of an **AI-powered Customer Support Operations Platform** designed for small and medium businesses. 

The platform empowers support teams to automatically classify incoming customer enquiries, extract semantic summaries, retrieve grounded policy information from uploaded company documents via **Retrieval-Augmented Generation (RAG)**, look up customer orders safely using **controlled backend tool calling**, and generate context-aware response drafts subject to **human staff review and approval**.

---

## 1. System Architecture

```
                                  +-----------------------------+
                                  |   React + TypeScript + Vite |
                                  |        (Tailwind CSS)       |
                                  +--------------+--------------+
                                                 | REST APIs
                                                 v
+-----------------------------------------------------------------------------------------------+
|                                    FastAPI Operations Backend                                 |
|                                                                                               |
|  +--------------------+   +-----------------------+   +-------------------+   +------------+  |
|  | Enquiry Management |   | Knowledge Base & RAG  |   | Order Lookup Tool |   | Audit Log  |  |
|  +---------+----------+   +-----------+-----------+   +---------+---------+   +-----+------+  |
|            |                          |                         |                   |         |
|            v                          v                         v                   v         |
|  +-----------------------------------------------------------------------------------------+  |
|  |                             Unified AI Operations Engine                                |  |
|  |  • Multi-class Intent & Sentiment Classifier                                            |  |
|  |  • Dense Vector Embeddings (OpenAI / Deterministic Semantic)                            |  |
|  |  • RAG Retrieval (Cosine Similarity & pgvector <=> index)                               |  |
|  |  • Safe Tool Dispatcher (lookup_order, search_customer_orders - zero raw SQL)           |  |
|  |  • Context-aware Draft Generator with Human Approval Gate                               |  |
|  |  • High-Fidelity Deterministic Demo Mode (clearly labelled when no API key configured)  |  |
|  +--------------------------------------------+--------------------------------------------+  |
+-----------------------------------------------|-----------------------------------------------+
                                                v
                    +-------------------------------------------------------+
                    |                      Data Layer                       |
                    |  • PostgreSQL 16 + pgvector (Production / Docker)     |
                    |  • SQLite Vector Math Fallback (Local Development)    |
                    +-------------------------------------------------------+
```

---

## 2. Key Features

- **Operations Dashboard**:
  - Live KPI metrics: Total Enquiries, Pending Triage, Awaiting Approval, Resolved.
  - Interactive category breakdown and priority distribution.
  - Real-time recent activity stream recording every ticket lifecycle event.
- **Enquiry Management**:
  - Full CRUD operations with search across customer name, email, subject, and order number.
  - Filter by status (`pending`, `in_review`, `awaiting_approval`, `resolved`, `rejected`) and category (`order_status`, `delivery`, `refund_return`, `company_policy`, `general_support`).
  - Channel tracking (`email`, `web_chat`, `contact_form`, `phone_transcription`).
- **AI Classification & Summarization**:
  - Automatic extraction of customer intent category, sentiment, and urgency priority.
  - Generates concise 1-2 sentence summaries and detects embedded order numbers.
  - Manual re-classification trigger button.
- **Knowledge Base & RAG**:
  - Upload PDF, TXT, and Markdown documents.
  - Text normalization, paragraph-aware chunking with sliding window overlap.
  - Vector embeddings stored with pgvector similarity indexing.
  - Grounded answer generation citing source document titles, chunk indices, and similarity scores.
  - Explicit warning when the knowledge base has insufficient confidence for a customer query.
  - Live **RAG Semantic Search Workbench** to test vector retrieval directly in the UI.
- **Safe Backend Tool Calling**:
  - Controlled `lookup_order` and `search_customer_orders` tools.
  - The LLM requests order status, carrier tracking, items, and delivery dates via strict backend function calls.
  - **Zero Arbitrary SQL**: Queries execute strictly via parameterized ORM filters.
- **Human-in-the-Loop Response Review**:
  - Staff workspace displaying the AI draft, grounding rationale, tool call logs, and citations.
  - Full inline editing of response drafts.
  - Staff actions: **Approve & Mark Resolved**, **Save Edits & Approve**, or **Reject Draft**.
  - **Safety guarantee**: Does not automatically send emails to customers without human authorization.
- **Immutable Audit Trail**:
  - Complete history of ticket creation, AI classification, draft generation, tool executions, and staff review decisions.

---

## 3. Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18/19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Axios |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Uvicorn |
| **Database** | PostgreSQL 16 with `pgvector` extension (plus SQLite fallback) |
| **AI & RAG** | Official Google Gen AI SDK (`google-genai`), Gemini 2.5 Flash, text-embedding-004, OpenAI (optional), Deterministic Demo Mode |
| **DevOps** | Docker, Docker Compose, GitHub Actions CI |

---

## 4. AI Provider Configuration: Google Gemini & Fallbacks

The platform supports **Google Gemini** as its primary AI provider via the official `google-genai` Python SDK, while keeping OpenAI available as a secondary provider and preserving the deterministic Demo Mode.

### Configuring Google Gemini

1. Obtain an API key from [Google AI Studio](https://aistudio.google.com/).
2. Add your key to `.env`:
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY="your-gemini-api-key"
   LLM_MODEL="gemini-2.5-flash"
   EMBEDDING_MODEL="text-embedding-004"
   EMBEDDING_DIMENSION=384
   ```
3. When `GEMINI_API_KEY` is set, Gemini powers:
   - **Enquiry classification and summarization** with structured JSON output.
   - **Context-aware response drafting** with function/tool calling (`lookup_order`).
   - **Text embeddings** via `text-embedding-004` with `output_dimensionality` matching the database vector column dimension (`384` or `768`).

### Deterministic Demo Mode (No API Key Required)

If `GEMINI_API_KEY` and `OPENAI_API_KEY` are unset or empty:
- The platform automatically operates in **Deterministic Demo Mode**.
- Every generated draft, classification, and rationale is clearly watermarked with `[DEMO MODE: Deterministic Operations Engine]`.
- The UI header displays a prominent **Demo Mode** indicator pill.
- If a live API call hits a rate limit (429) or quota exhaustion, it logs the warning and falls back to Demo Mode gracefully without crashing.

---

## 5. Quickstart & Local Execution

### Option A: Running with Docker Compose (Recommended)

Requires Docker Desktop running on your machine:

```bash
# 1. Clone the repository and navigate into it
cd "AI Operations Assistant"

# 2. Copy the environment template
cp .env.example .env

# 3. Launch all containers (Postgres with pgvector, Backend, Frontend)
docker compose up --build
```

- **Frontend Application**: [http://localhost:5173](http://localhost:5173) or [http://localhost:3000](http://localhost:3000)
- **FastAPI Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend API**: [http://localhost:8000/api/v1](http://localhost:8000/api/v1)

---

### Option B: Running Locally (Native Python & Node.js)

#### 1. Backend Setup:
```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate on Windows:
.\.venv\Scripts\activate
# Activate on Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run seed data script (seeds sample orders, policy documents, and initial tickets)
python -m backend.app.seed_data

# Start FastAPI development server (from inside backend/):
uvicorn app.main:app --reload --port 8000

# Or from project root:
# uvicorn backend.app.main:app --reload --port 8000
```

#### 2. Frontend Setup:
```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173) in your browser.

---

## 6. Running Automated Tests

A comprehensive test suite is provided covering API endpoints, RAG document search, controlled tool calling, and draft review workflows:

```bash
# Run backend pytest suite:
.\backend\.venv\Scripts\pytest backend\tests -v
```

Expected output:
```
backend/tests/test_documents_rag.py::test_list_documents PASSED          [ 10%]
backend/tests/test_documents_rag.py::test_upload_txt_document PASSED     [ 20%]
backend/tests/test_documents_rag.py::test_semantic_search_rag PASSED     [ 30%]
backend/tests/test_enquiries.py::test_list_enquiries PASSED              [ 40%]
backend/tests/test_enquiries.py::test_create_enquiry_with_auto_classification PASSED [ 50%]
backend/tests/test_enquiries.py::test_generate_draft_and_review_workflow PASSED [ 60%]
backend/tests/test_orders_tools.py::test_list_orders PASSED              [ 70%]
backend/tests/test_orders_tools.py::test_order_lookup_tool_by_number PASSED [ 80%]
backend/tests/test_orders_tools.py::test_order_lookup_tool_not_found PASSED [ 90%]
backend/tests/test_orders_tools.py::test_dashboard_analytics PASSED      [100%]
10 passed in 0.30s
```

Frontend production build check:
```bash
cd frontend
npm run build
```

---

## 7. API Reference Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service health, mode status, and LLM engine |
| `GET` | `/docs` | Interactive Swagger UI API documentation |
| `GET` | `/api/v1/analytics/dashboard` | Aggregated KPI stats and recent activity stream |
| `GET` | `/api/v1/enquiries` | List customer enquiries with filters (`status`, `category`, `search`) |
| `POST` | `/api/v1/enquiries` | Create customer enquiry (runs auto AI classification) |
| `GET` | `/api/v1/enquiries/{id}` | Get enquiry detail with drafts and audit trail |
| `PATCH` | `/api/v1/enquiries/{id}` | Update enquiry status, priority, or fields |
| `POST` | `/api/v1/enquiries/{id}/classify` | Re-run AI classification and intent extraction |
| `POST` | `/api/v1/enquiries/{id}/draft` | Generate AI response draft (RAG + tool calling) |
| `POST` | `/api/v1/enquiries/{id}/drafts/{draft_id}/review` | Staff review: approve, edit & approve, or reject |
| `GET` | `/api/v1/documents` | List ingested knowledge base documents |
| `POST` | `/api/v1/documents/upload` | Upload PDF/TXT, chunk, embed, and index for RAG |
| `DELETE` | `/api/v1/documents/{id}` | Delete document and indexed chunks |
| `POST` | `/api/v1/documents/search` | Query knowledge base chunks by cosine similarity |
| `GET` | `/api/v1/orders` | List sample business orders |
| `POST` | `/api/v1/orders/lookup` | Execute safe parameterized order lookup tool |
| `GET` | `/api/v1/audit` | Query system and staff audit history |

---

## 8. Continuous Integration (CI/CD)

GitHub Actions workflow is located at `.github/workflows/ci.yml`. On every push or pull request to `main`, it runs:
1. Python backend installation and `pytest` execution.
2. Node.js dependency installation, TypeScript typechecking, and Vite production bundle compilation.

---

## 9. Sample Test Walkthrough

1. **Dashboard**: Navigate to the **Dashboard** to see the 4 initial KPI cards, category breakdown, and recent audit activity.
2. **Review Awaiting Ticket**: In **Enquiry Inbox**, click on Ticket #1 (Alice Smith, `ORD-1002`). Notice the AI draft incorporates live order details (`DHL Express TRK-5519203`) and cites Chunk #1 of the Shipping Policy. Click **Approve & Mark Resolved**.
3. **Submit New Ticket**: Click **+ New Enquiry** in the top bar. Choose "Load Realistic Sample: Order Status (ORD-1003)". Submit. Notice the AI immediately classifies the intent as `order_status` with priority `medium`.
4. **Generate Draft**: Click **Generate AI Response Draft**. The backend invokes `lookup_order("ORD-1003")`, retrieves policy chunks, and produces a customer response draft.
5. **RAG Test**: Navigate to **Knowledge Base & RAG**, upload a custom text file or run a search query in the **Semantic Search Workbench** to verify similarity ranking.
6. **Tool Inspector**: Navigate to **Order Lookup** and execute tool calls for `ORD-1001` or `ORD-1002` to inspect the structured tool output payload.
7. **Audit Log**: Navigate to **Audit Trail** to inspect timestamped logs of every action.
