---
schema_version: 1
domain: engineering
implementation_summary: FastAPI + SQLAlchemy backend with plugin-pattern AI service layer; Next.js frontend with JWT auth
module_boundaries:
  - backend/app/api/v1/endpoints/   # FastAPI routers
  - backend/app/services/ai/        # AI orchestration (plugin pattern)
  - backend/app/services/ai/interfaces/  # Abstract contracts
  - backend/app/services/ai/providers/   # Concrete implementations
  - backend/app/models/             # SQLAlchemy ORM
  - backend/app/schemas/            # Pydantic request/response
  - backend/app/core/               # Config, security, JWT
  - frontend/app/                   # Next.js pages
  - frontend/components/ai/         # AI chat components
implementation_units:
  - backend/app/services/ai/factory.py           # Provider instantiation
  - backend/app/services/ai/policy_rag.py        # RAG pipeline
  - backend/app/services/ai/sql_agent.py         # NL-to-SQL
  - backend/app/services/ai/sql_guardrails.py    # SQL validation
  - backend/app/services/ai/action_agent.py      # HR action automation
  - backend/app/services/ai/api_tools.py         # Service layer wrappers
  - backend/app/services/ai/router_agent.py      # Intent classification
  - backend/app/services/ai/permissions.py       # Role-based AI permissions
  - backend/app/services/ai/audit.py             # Audit logging
  - backend/app/api/v1/endpoints/chat.py         # Chat HTTP endpoints
interface_contracts:
  - BaseLLMProvider (interfaces/llm.py)
  - BaseEmbedder (interfaces/embedder.py)
  - BaseVectorStore (interfaces/vector_store.py)
  - AuditLog (models/ai_audit_log.py → ai_audit_logs table)
  - ChatRequest/ChatResponse (schemas/chat.py)
hotspots:
  - backend/app/services/ai/sql_guardrails.py    # forbidden column enforcement
  - backend/app/services/ai/permissions.py       # RBAC gate
  - backend/app/services/ai/factory.py           # provider selection
  - backend/app/core/dependencies.py             # get_current_user, require_role
test_touchpoints:
  - backend/tests/unit/test_prompt_injection_defense.py
  - backend/tests/unit/test_hr_data_rag.py
  - backend/tests/unit/test_leave_service.py
  - backend/tests/unit/test_policy_rag_rbac.py
  - backend/tests/unit/test_action_agent_parse.py
implementation_invariants:
  - factory.py never imports concrete providers at module level — lazy import on first call
  - sql_guardrails.validate_sql() called before execution, scrub_forbidden_columns() called after — both required
  - can_perform() always called before any action dispatch in action_agent.py
  - audit.log_interaction() called in finally block of every chat endpoint handler
---

# Low-Level Architecture — NovaWorks PeopleOps Copilot

## Module Boundaries

### Backend

```
backend/app/
├── api/v1/endpoints/
│   ├── chat.py          ← all AI chat endpoints (policy/sql/actions/router/hr-data)
│   ├── auth.py          ← login, refresh, /me
│   ├── leaves.py        ← leave requests + approvals
│   ├── tickets.py       ← ticket CRUD
│   ├── announcements.py ← announcement creation
│   ├── projects.py      ← project + employee-project assignment
│   └── admin.py         ← admin-only endpoints
├── core/
│   ├── config.py        ← Settings (pydantic BaseSettings, reads .env)
│   ├── security.py      ← JWT encode/decode, password hashing
│   └── dependencies.py  ← get_current_user(), require_role(), get_db()
├── db/
│   ├── session.py       ← SQLAlchemy engine + SessionLocal
│   └── base.py          ← declarative_base
├── models/              ← SQLAlchemy ORM models
│   ├── employee.py      ← Employee (includes forbidden columns — never select *)
│   ├── leave.py         ← LeaveRequest, LeaveBalance
│   ├── ai_audit_log.py  ← AIAuditLog
│   └── ...
├── schemas/             ← Pydantic request/response models
│   ├── chat.py          ← ChatRequest, PolicyResponse, SQLResponse, ActionResponse
│   └── ...
└── services/ai/
    ├── interfaces/       ← Abstract base classes (the contract)
    │   ├── llm.py        → BaseLLMProvider
    │   ├── embedder.py   → BaseEmbedder
    │   └── vector_store.py → BaseVectorStore
    ├── providers/        ← Concrete implementations
    │   ├── llm/anthropic.py, openai_llm.py
    │   ├── embedders/voyage.py, openai_embedder.py
    │   └── vector_stores/chroma.py, faiss_store.py
    ├── factory.py        ← Config-driven provider selection
    ├── policy_rag.py     ← RAG pipeline
    ├── sql_agent.py      ← NL-to-SQL with role filtering
    ├── sql_guardrails.py ← Pre/post SQL validation
    ├── action_agent.py   ← Intent extraction + dispatch
    ├── api_tools.py      ← Service layer wrappers (called by action_agent)
    ├── router_agent.py   ← Intent classification → delegate
    ├── permissions.py    ← can_perform(user, action) → bool + reason
    ├── audit.py          ← log_interaction() → ai_audit_logs
    └── memory.py         ← conversation_memory table
```

### Frontend

```
frontend/
├── app/
│   ├── ai-copilot/page.tsx  ← main AI copilot page, mode selector
│   ├── login/page.tsx
│   ├── admin/page.tsx
│   └── layout.tsx           ← root layout with sidebar nav
├── components/ai/
│   ├── ChatPanel.tsx        ← message input + history
│   ├── SourceList.tsx       ← policy RAG source citations
│   ├── SQLResultTable.tsx   ← tabular SQL results
│   ├── ActionResultCard.tsx ← HR action confirmation
│   ├── PendingApprovals.tsx ← manager-only leave approvals
│   ├── MyLeaves.tsx         ← employee leave history
│   ├── MyProjects.tsx
│   ├── MyTickets.tsx
│   └── Announcements.tsx
└── lib/
    ├── api.ts               ← API client (wraps fetch with JWT)
    └── auth.ts              ← JWT storage + decode
```

## Interface Contracts

### BaseLLMProvider (interfaces/llm.py)
```python
async def chat(messages: list[dict], **kwargs) -> str
async def stream_chat(messages: list[dict], **kwargs) -> AsyncIterator[str]
```

### BaseEmbedder (interfaces/embedder.py)
```python
async def embed(texts: list[str]) -> list[list[float]]
```

### BaseVectorStore (interfaces/vector_store.py)
```python
async def add_documents(docs: list[Document]) -> None
async def similarity_search(query_embedding: list[float], k: int) -> list[Document]
async def clear() -> None
```

## Critical Sequences

### Adding a new LLM provider
1. Create `providers/llm/newprovider.py` implementing `BaseLLMProvider`
2. Register in `factory.py` provider map
3. Set `AI_LLM_PROVIDER=newprovider` in `.env`
4. Zero other file changes

### Adding a new forbidden SQL column
1. Add to `FORBIDDEN_COLUMNS` list in `sql_guardrails.py` (pre-execution block)
2. Add to `scrub_forbidden_columns()` in `sql_guardrails.py` (post-execution scrub)
3. Both layers must be updated — defence-in-depth

### Adding a new action tool
1. Implement service function in `api_tools.py`
2. Add permission rule in `permissions.py` (can_perform mapping)
3. Add dispatch case in `action_agent.py`
4. Tests: add to `test_action_agent_parse.py`
