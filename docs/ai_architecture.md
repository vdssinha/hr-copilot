# AI Architecture — NovaWorks PeopleOps Copilot

## Overview

Three AI capabilities sit behind a unified router, all gated by JWT auth and RBAC:

```
┌──────────────────────────────────────────────────────────────────┐
│                       NEXT.JS FRONTEND                           │
│  /ai-copilot — mode selector:                                    │
│    router | policy | sql | actions | hr-data (chat modes)        │
│    my-leaves (all roles) | pending-approvals (manager+)          │
│  Components: ChatPanel / SourceList / SQLResultTable /           │
│    ActionResultCard / PendingApprovals / MyLeaves                │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ JWT Bearer
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                             │
│  AI Chat endpoints:                                              │
│  POST /api/v1/chat/router         ← unified intent classifier    │
│  POST /api/v1/chat/policy         ← Policy RAG                   │
│  POST /api/v1/chat/sql            ← SQL Agent                    │
│  POST /api/v1/chat/actions        ← HR Action Agent              │
│  POST /api/v1/chat/router/stream  ← NDJSON streaming             │
│  POST /api/v1/chat/hr-data        ← Semantic HR CSV search       │
│  POST /api/v1/chat/policy/ingest  ← admin: re-index policies     │
│                                                                  │
│  HR REST API (called by agents + direct UI):                     │
│  POST   /api/v1/leaves/requests        ← apply leave             │
│  PATCH  /api/v1/leaves/requests/{id}   ← approve/reject          │
│  GET    /api/v1/leaves/requests/my     ← own leave history       │
│  GET    /api/v1/leaves/requests/pending ← pending approvals      │
│  POST   /api/v1/tickets               ← create ticket            │
│  PATCH  /api/v1/tickets/{id}          ← assign/update ticket     │
│  GET    /api/v1/tickets/my            ← own tickets              │
│  POST   /api/v1/announcements         ← create announcement      │
│  POST   /api/v1/employees/{id}/projects ← assign to project      │
│  GET    /api/v1/projects/my           ← own project assignments  │
│  POST   /api/v1/projects             ← create project (ADMIN)    │
│  GET    /api/v1/projects/employees   ← team project mapping      │
└──────────────────────────────────┬───────────────────────────────┘
                                   │
                         ┌─────────┴──────────┐
                         ▼                    ▼
              ┌──────────────────┐   ┌────────────────────────┐
              │   AI Service     │   │   Auth / RBAC          │
              │   Layer          │   │   get_current_user()   │
              │                  │   │   require_role()       │
              │  router_agent    │   │   can_perform()        │
              │  policy_rag      │   └────────────────────────┘
              │  sql_agent       │
              │  action_agent    │
              │  audit           │
              └────────┬─────────┘
                       │
         ┌─────────────┼──────────────┐
         ▼             ▼              ▼
  ┌────────────┐ ┌──────────┐ ┌───────────────┐
  │  LLM       │ │ Embedder │ │ Vector Store  │
  │  Provider  │ │ Provider │ │ Provider      │
  │ (abstract) │ │(abstract)│ │  (abstract)   │
  └─────┬──────┘ └────┬─────┘ └──────┬────────┘
        │              │              │
  OpenAI/Anthropic  OpenAI/Voyage  ChromaDB/FAISS
```

## Plugin / Strategy Pattern

All AI providers are swappable via `.env` — no code changes:

| Config key              | Default (dev)                         | Supported values            |
|-------------------------|---------------------------------------|-----------------------------|
| `AI_LLM_PROVIDER`       | `openai`                              | `openai`, `anthropic`       |
| `AI_EMBEDDER_PROVIDER`  | `openai`                              | `openai`, `anthropic`       |
| `AI_VECTOR_STORE_PROVIDER` | `chroma`                           | `chroma`, `faiss`           |
| `AI_LLM_MODEL`          | `google/gemma-4-31b`                  | any model ID                |
| `AI_EMBEDDING_MODEL`    | `text-embedding-nomic-embed-text-v1.5`| any embedding model ID      |

`factory.py` reads config and returns the correct concrete provider without callers knowing the implementation.

## AI Features

### 1. Policy RAG (`policy_rag.py`)

```
User question
     │
     ▼
embed_query(question)          ← Embedder provider
     │
     ▼
similarity_search(k=5)         ← Vector store
     │ threshold 1.2 (cosine)
     ▼
Retrieved chunks (top-k)
     │
     ▼
LLM grounded generation        ← LLM provider
     │  system: cite sources, refuse if ungrounded,
     │          treat retrieved text as untrusted
     ▼
PolicyResult { answer, sources, source_count }
```

Policies are ingested from `backend/data/policies/*.md`. Chunking: 800 chars / 100 overlap (`RecursiveCharacterTextSplitter`). Embeddings stored in ChromaDB with policy metadata.

### 2. SQL Agent (`sql_agent.py` + `sql_guardrails.py`)

```
User question
     │
     ▼
Build schema block + access rules (role-filtered)
     │
     ▼
LLM → SELECT statement          ← LLM provider
     │
     ▼
validate_sql()                  ← sql_guardrails
  ├─ Block DDL / DML keywords
  ├─ Enforce SELECT only
  ├─ Reject forbidden columns
  ├─ Reject unbalanced parentheses
  └─ Inject LIMIT 100
     │
     ▼
Execute on SQLite (read-only intent)
     │
     ▼
scrub_forbidden_columns()       ← defence-in-depth
     │
     ▼
LLM NL summary                  ← LLM provider
     │
     ▼
SQLResult { answer, sql, rows, row_count }
```

Access rules injected into the system prompt — EMPLOYEE sees only own rows, MANAGER sees team, ADMIN sees all.

### 3. HR Action Agent (`action_agent.py` + `api_tools.py`)

```
User message
     │
     ▼
LLM intent extraction → JSON { action, params, cannot_do_reason }
     │  _parse_llm_json: strips fences, extracts first {...} block
     │
     ▼
Permission check (can_perform + cannot_do_reason)
     │
     ▼
Permission check (can_perform + cannot_do_reason)
     │
     ▼
Dispatch to api_tools → service layer (same process, equivalent to REST API call)
  Mutations: apply_leave / approve_leave / reject_leave / create_ticket /
             assign_ticket / create_announcement / assign_employee_to_project /
             create_project
  Queries:   check_leave_balance / get_my_leaves / list_pending_approvals /
             check_ticket_status / view_own_projects / search_employees_by_skill /
             check_project_assignments
     │
     ▼  (service layer = same logic as REST endpoints below)
LLM result summary
     │
     ▼
ActionResult { answer, action, success, data }
```

All mutations flow through `app/services/*_service.py` — the same service layer
called by the HR REST endpoints. Never raw SQL writes from the agent.

Architecture: **Agent → Service Layer → DB** (equivalent to Agent → REST API → Service Layer → DB)

### 4. Router Agent (`router_agent.py`)

Classifies message into `POLICY_QA | SQL_QUERY | HR_ACTION | UNKNOWN` then delegates to the appropriate agent. One LLM call for classification + one for execution.

## Audit Logging

Every AI interaction writes to `ai_audit_logs`:

```
user_id | role | message | intent | tool_used | action_status | answer_preview | created_at
```

No secrets, passwords, or sensitive data logged. Stored in SQLite, queryable by admin.

## Local Dev Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- LM Studio (or Anthropic/OpenAI API key)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure providers
cp .env.example .env
# Edit .env — see Environment Variables section

# Initialize DB + seed data
python scripts/seed.py

# Start server
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

### LM Studio Setup (local inference)

1. Download LM Studio, load `google/gemma-4-31b` (or any GGUF model)
2. Load `nomic-embed-text-v1.5` for embeddings
3. Start the local server on port 1234

```env
AI_LLM_PROVIDER=openai
AI_EMBEDDER_PROVIDER=openai
AI_LLM_MODEL=google/gemma-4-31b
AI_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
OPENAI_API_KEY=lm-studio
OPENAI_BASE_URL=http://localhost:1234/v1
```

## Environment Variables

| Variable                   | Required | Description                                        |
|----------------------------|----------|----------------------------------------------------|
| `AI_LLM_PROVIDER`          | yes      | `openai` or `anthropic`                            |
| `AI_EMBEDDER_PROVIDER`     | yes      | `openai` or `anthropic`                            |
| `AI_VECTOR_STORE_PROVIDER` | yes      | `chroma` or `faiss`                                |
| `AI_LLM_MODEL`             | yes      | Model ID (passed to provider)                      |
| `AI_EMBEDDING_MODEL`       | yes      | Embedding model ID                                 |
| `OPENAI_API_KEY`           | if openai| API key (use any string for LM Studio)             |
| `OPENAI_BASE_URL`          | no       | Override base URL (e.g. `http://localhost:1234/v1`)|
| `ANTHROPIC_API_KEY`        | if anthropic | Anthropic API key                              |
| `VOYAGE_API_KEY`           | if anthropic embedder | Voyage AI key (falls back to ANTHROPIC_API_KEY) |
| `CHROMA_PERSIST_DIR`       | yes      | Path to ChromaDB storage                          |
| `DATABASE_URL`             | yes      | SQLAlchemy URL (default: `sqlite:///./cbnest.db`)  |
| `SECRET_KEY`               | yes      | JWT signing secret                                 |

## AI Endpoint Contracts

### POST /api/v1/chat/policy

```json
Request:  { "message": "What is the leave policy?" }
Response: {
  "answer": "...",
  "sources": [{ "policy_name": "...", "section": "...", "content": "..." }],
  "source_count": 2
}
```

### POST /api/v1/chat/sql

```json
Request:  { "message": "Which projects are ongoing?" }
Response: {
  "answer": "...",
  "sql": "SELECT ...",
  "rows": [...],
  "row_count": 3
}
```

### POST /api/v1/chat/actions

```json
Request:  { "message": "Apply sick leave from 2026-05-10 to 2026-05-12" }
Response: {
  "answer": "...",
  "action": "apply_leave",
  "success": true,
  "data": { ... }
}
```

### POST /api/v1/chat/router

```json
Request:  { "message": "How many sick leaves do I get?" }
Response: {
  "answer": "...",
  "intent": "POLICY_QA",
  "sources": [...],      // if POLICY_QA
  "sql": "...",          // if SQL_QUERY
  "rows": [...],         // if SQL_QUERY
  "action": "...",       // if HR_ACTION
  "success": true/false  // if HR_ACTION
}
```

All endpoints require `Authorization: Bearer <jwt>`.

## Security Decisions

1. **Forbidden columns hard-coded in two places** — `sql_guardrails.py` (pre-execution validation) and `scrub_forbidden_columns()` (post-execution row scrub). Defence-in-depth: even if guardrail is bypassed, column never reaches the response.

2. **No raw SQL writes from agents** — Action agent calls service functions that use SQLAlchemy ORM with session-level constraints. Only SELECT queries reach the DB via the SQL agent.

3. **Access rules in LLM system prompt** — Role-specific WHERE clause instructions reduce probability of the model generating cross-user queries. Guardrail layer is the hard enforcement.

4. **Prompt injection defence in RAG** — System prompt instructs LLM to treat retrieved chunk text as untrusted document content, not instructions.

5. **RBAC enforced server-side** — `can_perform()` checks happen in Python after JWT decode, not in the frontend and not delegated to the LLM.

6. **No secrets in logs** — Audit log captures `message` and `answer_preview` (first 500 chars) but excludes tokens, keys, and credentials.

## Known Limitations

- **LM Studio / thinking models**: Gemma and similar models that use chain-of-thought may exhaust token budgets on reasoning. Mitigation: `reasoning_content` fallback in `openai_llm.py` extracts the final draft.
- **SQL access rules are advisory**: Role filtering is injected into the LLM prompt. A sufficiently adversarial user message could attempt to bypass. Guardrails block DDL/DML but cannot guarantee correct row-level filtering in all cases.
- **ChromaDB is local**: Not suitable for multi-instance deployment without a shared volume or switching to a hosted vector DB (config change only).
- **Policy ingest is idempotent but not incremental**: Re-ingest clears and reloads all policies. Large policy sets will be slow.
- **No streaming**: All responses are synchronous. For long SQL summaries or policy answers, latency can be noticeable.
