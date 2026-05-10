# hrCopilot Backend — Architecture Overview

## What This System Does

CB Nest is a conversational HR assistant for NovaWorks Technologies. Employees, managers, and admins ask natural-language questions. The backend classifies each question, routes it to the right AI agent, and returns a grounded answer. Every interaction is audit-logged.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| Database | SQLite via SQLAlchemy + Alembic |
| LLM (default) | Anthropic Claude (claude-sonnet-4-6) |
| Embeddings (default) | Voyage AI (voyage-3) |
| Vector store (default) | ChromaDB (local persistent) |
| Auth | JWT (HS256) via python-jose |
| Password hashing | bcrypt via passlib |

All three AI providers (LLM, embedder, vector store) are **swappable via config**. Adding a new provider requires only: a new implementation file + updating `AI_LLM_PROVIDER` / `AI_EMBEDDER_PROVIDER` / `AI_VECTOR_STORE_PROVIDER` in `.env`. No other code changes.

---

## Directory Map

```
backend/app/
├── main.py                        # FastAPI app entry point
├── core/
│   ├── config.py                  # All config — single source of truth
│   ├── security.py                # JWT + bcrypt helpers
│   └── dependencies.py            # FastAPI dependency injectors (auth, role guards)
├── db/
│   ├── session.py                 # SQLAlchemy engine + session factory
│   └── base.py                    # Declarative base
├── models/                        # SQLAlchemy ORM models (one table per file)
│   ├── employee.py                # Core: Employee, EmployeeRole, EmployeeStatus
│   ├── hr_policy.py               # HRPolicy, PolicyCategory
│   ├── leave.py                   # LeaveRequest, LeaveBalance, LeaveType
│   ├── payroll.py                 # PayrollRecord
│   ├── ticket.py                  # Ticket, TicketCategory, TicketPriority
│   ├── announcement.py            # Announcement, AnnouncementCategory
│   ├── project.py                 # Project, EmployeeProject
│   ├── skill.py                   # Skill, EmployeeSkill
│   ├── job_history.py             # JobHistory
│   ├── onboarding.py              # OnboardingTask
│   ├── department.py              # Department
│   ├── ai_audit_log.py            # AIAuditLog, AIIntent, ActionStatus
│   ├── role_category_access.py    # RoleCategoryAccess (role→policy categories)
│   └── policy_group.py            # PolicyGroup, GroupCategoryAccess
├── schemas/                       # Pydantic request/response shapes
│   ├── auth.py                    # LoginRequest, TokenResponse, RegisterRequest
│   ├── chat.py                    # ChatRequest
│   ├── admin.py                   # Admin CRUD schemas
│   └── common.py                  # APIResponse (unified envelope)
├── api/v1/
│   ├── router.py                  # Mounts auth, chat, admin routers under /api/v1
│   └── endpoints/
│       ├── auth.py                # POST /auth/login, /auth/register
│       ├── chat.py                # All /chat/* endpoints
│       └── admin.py               # All /admin/* endpoints
└── services/ai/
    ├── factory.py                 # Provider factory — instantiates LLM/embedder/vector store
    ├── router_agent.py            # Intent classifier + dispatcher
    ├── policy_rag.py              # RAG pipeline for HR policy questions
    ├── sql_agent.py               # NL→SQL agent for structured data queries
    ├── hr_data_rag.py             # Semantic search over hr_data.csv
    ├── action_agent.py            # Task automation (leave, tickets, announcements)
    ├── langgraph_agent.py         # LangGraph graph wrapping the same agents
    ├── audit.py                   # Write AIAuditLog entries
    ├── context.py                 # Build conversation history block for LLM prompts
    ├── permissions.py             # Role→allowed-actions map
    ├── sql_guardrails.py          # SQL safety: block DDL, forbidden columns, cap rows
    ├── document_loader.py         # Extract text from .md/.txt/.pdf/.docx
    ├── api_tools.py               # In-process tool implementations for action agent
    ├── interfaces/
    │   ├── llm.py                 # BaseLLMProvider ABC
    │   ├── embedder.py            # BaseEmbedder ABC
    │   └── vector_store.py        # BaseVectorStore ABC + Document dataclass
    └── providers/
        ├── llm/
        │   ├── anthropic.py       # AnthropicProvider
        │   └── openai_llm.py      # OpenAIProvider (also LM Studio / local models)
        ├── embedders/
        │   ├── voyage.py          # VoyageEmbedder
        │   └── openai_embedder.py # OpenAIEmbedder
        └── vector_stores/
            ├── chroma.py          # ChromaVectorStore (persistent, default)
            └── faiss_store.py     # FAISSVectorStore (in-memory, no persistence)
```

---

## Request Lifecycle — Happy Path

### Chat query via `/api/v1/chat/router`

```
Browser / Frontend
    │
    │  POST /api/v1/chat/router  {message, history[]}
    ▼
FastAPI — chat.py:chat_router()
    │  Dependency injection:
    │   • get_current_user() → decodes JWT → loads Employee from DB
    │   • get_db()           → opens SQLAlchemy session
    │
    ▼
router_agent.py:route_and_answer()
    │
    ├─ Step 1: classify_intent(message)
    │     └─ LLM call #1 (Anthropic, 512 tokens max)
    │        System: intent classifier prompt
    │        Returns: {intent, confidence, reason}
    │
    ├─ Branch on intent:
    │
    │  POLICY_QA ──► policy_rag.py:answer_policy_question()
    │                 ├─ _needs_ingestion() check (ChromaDB count + DB)
    │                 ├─ _get_accessible_categories() (DB query, enforces RBAC)
    │                 ├─ embedder.embed_query(question)  ← Voyage AI API call
    │                 ├─ store.similarity_search(embedding, k=5, where=categories)
    │                 └─ LLM call #2 (Anthropic, 1024 tokens max)
    │                    Returns: {answer, sources[]}
    │
    │  SQL_QUERY ──► sql_agent.py:run_sql_query()
    │                 ├─ _build_access_rules(user) → role-based WHERE constraints
    │                 ├─ LLM call #1 (Anthropic, 512 tokens) → raw SQL
    │                 ├─ _extract_sql() → parse + sentinel check
    │                 ├─ validate_sql() → guardrails (DDL block, forbidden cols, LIMIT cap)
    │                 ├─ db.execute(text(sql)) → SQLite
    │                 ├─ scrub_forbidden_columns(rows) → defence-in-depth
    │                 └─ LLM call #2 (Anthropic, 256 tokens) → NL summary
    │                    Returns: {answer, sql, rows[], row_count}
    │
    │  HR_ACTION ──► action_agent.py:run_action()
    │                 ├─ LLM call #1 (Anthropic, 1024 tokens) → extract {action, params}
    │                 ├─ can_perform(user, action) → permissions.py check
    │                 ├─ dispatch → api_tools.py function (DB write)
    │                 └─ LLM call #2 (Anthropic, 500 tokens) → NL confirmation
    │                    Returns: {answer, action, success, data}
    │
    ▼
audit.py:log_ai_interaction()
    └─ INSERT into ai_audit_logs

    ▼
APIResponse.ok(result)  →  {status: "ok", data: {...}}
```

**Total external API calls per query:**
- POLICY_QA: 2 (classify + answer)
- SQL_QUERY: 2 (SQL gen + summary) — no embedding needed
- HR_ACTION: 2 (extract + summary)

All calls are sequential. The Voyage AI embed call adds a third network round-trip for POLICY_QA (classify → embed → answer).

---

## Authentication Flow

```
POST /auth/login  {email, password}
    │
    ├─ Load Employee by email
    ├─ verify_password(plain, hashed)   ← bcrypt
    ├─ create_access_token({sub: user.id, role: user.role})  ← JWT HS256
    └─ Return {access_token, role, user_id, name}

Protected endpoints:
    Authorization: Bearer <token>
    │
    ├─ HTTPBearer extracts token
    ├─ decode_token(token)  → {sub, role, exp}
    ├─ Query Employee WHERE id=sub AND status=ACTIVE
    └─ Inject Employee into endpoint handler
```

---

## RBAC — Two Levels

### 1. Action permissions (chat/actions endpoint)
Defined in `permissions.py`. Each role maps to a frozenset of allowed action strings.

| Role | Extra actions beyond base |
|---|---|
| EMPLOYEE / MARKETING | apply_leave, check_leave_balance, create_ticket |
| MANAGER / HR / C_LEVEL | + approve_leave, reject_leave, assign_ticket, create_announcement, assign_employee_to_project |
| ADMIN | + create_project |

### 2. Policy category access (chat/policy endpoint)
Two-tier system in DB:
- **Role-based**: `role_category_access` table maps `EmployeeRole` → `PolicyCategory`
- **Group-based**: `group_category_access` table maps a named policy group → categories (overrides role if set on Employee)

Admin can manage both via `/admin/roles` and `/admin/policy-groups`.

---

## Provider Plugin System

Three plugin points, each with an ABC interface:

```
BaseLLMProvider   →  AnthropicProvider | OpenAIProvider
BaseEmbedder      →  VoyageEmbedder   | OpenAIEmbedder
BaseVectorStore   →  ChromaVectorStore | FAISSVectorStore
```

All resolved in `factory.py` via env vars. To add a new provider:
1. Create `providers/<type>/<name>.py` implementing the ABC
2. Add a branch in `factory.py`
3. Set the env var

No changes to calling code (router_agent, policy_rag, etc.).

---

## Vector Collections

Two separate collections in the vector store:

| Collection | Contents | Populated by |
|---|---|---|
| `hr_policies` | Chunked HR policy documents (800 char chunks, 100 overlap) | `policy_rag.ingest_policies()` — auto on first query or on upload |
| `hr_data` | One document per employee row from `hr_data.csv` | `hr_data_rag.ingest_hr_data()` — triggered via admin endpoint |

---

## Audit Logging

Every AI interaction writes one `ai_audit_logs` row via `audit.log_ai_interaction()`:
- `user_id`, `role`, `message` — who asked what
- `intent` — classified intent (POLICY_QA / SQL_QUERY / HR_ACTION / UNKNOWN / ROUTER)
- `action_status` — SUCCESS / REFUSED / ERROR
- `tool_name` — which agent handled it
- `records_accessed` — JSON list of policy titles or SQL strings accessed

---

## Endpoints Summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/login` | — | Get JWT |
| POST | `/auth/register` | — | Create account |
| POST | `/chat/policy` | Bearer | Policy RAG query |
| POST | `/chat/sql` | Bearer | NL→SQL data query |
| POST | `/chat/actions` | Bearer | HR action automation |
| POST | `/chat/router` | Bearer | Auto-classify + dispatch |
| POST | `/chat/router/stream` | Bearer | NDJSON streaming version of router |
| POST | `/chat/langgraph` | Bearer | LangGraph orchestration (same logic) |
| POST | `/chat/hr-data` | Bearer | Semantic search over hr_data.csv |
| POST | `/chat/policy/ingest` | Bearer (ADMIN) | Re-embed all policies |
| GET | `/admin/users` | Bearer (ADMIN) | List all employees |
| POST | `/admin/users` | Bearer (ADMIN) | Create employee |
| PATCH | `/admin/users/{id}` | Bearer (ADMIN) | Update employee |
| DELETE | `/admin/users/{id}` | Bearer (ADMIN) | Delete employee (cascades) |
| GET | `/admin/roles` | Bearer (ADMIN) | List role→category mappings |
| PATCH | `/admin/roles/{role}` | Bearer (ADMIN) | Update role's accessible categories |
| GET | `/admin/categories` | Bearer (ADMIN) | List category→role mappings |
| PATCH | `/admin/categories/{cat}` | Bearer (ADMIN) | Update category's accessible roles |
| GET | `/admin/policies` | Bearer (ADMIN) | List all HR policies |
| POST | `/admin/policies/upload` | Bearer (ADMIN) | Upload + ingest new policy |
| DELETE | `/admin/policies/{id}` | Bearer (ADMIN) | Delete policy + purge from vector store |
| GET | `/admin/policy-groups` | Bearer (ADMIN) | List policy groups |
| POST | `/admin/policy-groups` | Bearer (ADMIN) | Create policy group |
| PATCH | `/admin/policy-groups/{name}` | Bearer (ADMIN) | Update group's categories |
| DELETE | `/admin/policy-groups/{name}` | Bearer (ADMIN) | Delete group |
| POST | `/admin/hr-data/ingest` | Bearer (ADMIN) | Re-ingest hr_data.csv |
| GET | `/health` | — | Health check |

---

## Key Design Invariants

1. **No raw DB errors leak to callers.** SQL agent catches all execution errors and returns safe messages.
2. **Forbidden columns** (`hashed_password`, `pan_number`, bank fields, etc.) are blocked at two levels: SQL generation prompt + post-execution `scrub_forbidden_columns()`.
3. **All SQL is SELECT-only.** `validate_sql()` blocks DDL/DML before any query reaches SQLite.
4. **Row cap.** SQL agent injects `LIMIT 100` if missing; caps any user-specified LIMIT at 100.
5. **Policy access is DB-driven.** Categories accessible to a role/group are stored in the DB, editable by admin — no hardcoded role→content mapping.
6. **Conversation history is bounded.** `build_history_block()` trims to the last `AI_CONTEXT_TURNS` (default 3) user+assistant pairs.
