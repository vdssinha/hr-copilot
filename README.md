# NovaWorks PeopleOps Copilot

AI-powered HR operations assistant built on top of the CB Nest HRMS platform.  
DS Bootcamp assignment — full-stack AI feature integration.

---

## Demo

[![Watch Demo](https://img.shields.io/badge/▶%20Watch%20Demo%20Video-Google%20Drive-blue?style=for-the-badge&logo=google-drive)](https://drive.google.com/file/d/1TZ2wDdpcVcJFAXxjaJZuu7jHenEfoQ7l/view?usp=drive_link)

---

## What It Does

Natural language interface over three AI capabilities:

| Capability | What it does |
|-----------|-------------|
| **Policy RAG** | Answers HR policy questions with grounded citations from the policy library |
| **SQL Agent** | Retrieves HR data (projects, skills, leave, employees) using safe read-only SQL |
| **Action Agent** | Performs HR tasks (apply leave, create ticket, announce, approve, assign) via chat |
| **Router** | Unified endpoint that auto-classifies intent and routes to the right agent |

All features are gated by JWT auth and role-based access control (EMPLOYEE / MANAGER / ADMIN).

Policy RAG now enforces **document-level RBAC** — categories are filtered at the vector store query level so restricted policy chunks are never returned to unauthorised roles.

An **Admin Portal** (`/admin`) lets ADMIN users manage users, upload policy documents, and configure which roles can access which policy categories — all without code changes.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI, SQLAlchemy (sync), SQLite, Alembic |
| AI providers | Anthropic Claude / OpenAI-compatible (config-driven) |
| Embeddings | Voyage AI / OpenAI / LM Studio nomic-embed (config-driven) |
| Vector store | ChromaDB / FAISS (config-driven) |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |

All AI providers use a **plugin/strategy pattern** — swap any provider via `.env`, no code changes.

---

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 18+
- One of: Anthropic API key, OpenAI API key, or LM Studio running locally

### Backend

```bash
cd backend

# 1. Create virtualenv and install dependencies
uv venv
uv pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your provider settings (see Provider Setup below)

# 3. Apply DB migrations
uv run --env-file .env alembic upgrade head

# 4. Seed database + ingest policies
uv run --env-file .env python scripts/seed.py

# 5. Start server
uv run --env-file .env uvicorn app.main:app --reload
# → http://localhost:8000
```

> **Running tests**
> ```bash
> uv run --env-file .env python -m pytest tests/ -v
> ```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
# → http://localhost:3000
```

Navigate to `http://localhost:3000/ai-copilot` for the copilot, or `http://localhost:3000/admin` for the admin portal.

Log in with a seeded account:

| Email | Password | Role |
|-------|----------|------|
| rahul.verma@novaworks.in | password123 | EMPLOYEE |
| arjun.mehta@novaworks.in | password123 | MANAGER |
| priya.sharma@novaworks.in | password123 | ADMIN |

---

## Provider Setup

### LM Studio (local inference)

1. Download and open LM Studio
2. Load `google/gemma-4-31b` (or any instruction-following GGUF)
3. Load `nomic-embed-text-v1.5` for embeddings
4. Start the local server on port 1234

```env
AI_LLM_PROVIDER=openai
AI_EMBEDDER_PROVIDER=openai
AI_LLM_MODEL=google/gemma-4-31b
AI_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
OPENAI_API_KEY=lm-studio
OPENAI_BASE_URL=http://localhost:1234/v1
```

### Anthropic + Voyage

```env
AI_LLM_PROVIDER=anthropic
AI_EMBEDDER_PROVIDER=anthropic
AI_LLM_MODEL=claude-sonnet-4-6
AI_EMBEDDING_MODEL=voyage-3
ANTHROPIC_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...
```

---

## API Endpoints

All endpoints require `Authorization: Bearer <jwt>`.

```
POST /api/v1/auth/login                      login → JWT
POST /api/v1/chat/policy                     Policy RAG (role-filtered)
POST /api/v1/chat/sql                        SQL Agent
POST /api/v1/chat/actions                    HR Action Agent
POST /api/v1/chat/router                     Unified router (auto-classify)
POST /api/v1/chat/router/stream              Streaming NDJSON router
POST /api/v1/chat/hr-data                    HR data RAG (manager/admin)
POST /api/v1/chat/langgraph                  LangGraph multi-agent orchestration
POST /api/v1/chat/policy/ingest              Re-index policies (admin only)

# Admin (ADMIN role only)
GET  /api/v1/admin/users                     List employees
POST /api/v1/admin/users                     Create employee
PATCH /api/v1/admin/users/{id}               Update employee
DELETE /api/v1/admin/users/{id}              Delete employee

GET  /api/v1/admin/roles                     List roles + category access
PATCH /api/v1/admin/roles/{name}             Update role's accessible categories

GET  /api/v1/admin/categories                List categories + role access
PATCH /api/v1/admin/categories/{name}        Update category's accessible roles

GET  /api/v1/admin/policies                  List policies
POST /api/v1/admin/policies/upload           Upload + ingest policy file
DELETE /api/v1/admin/policies/{id}           Deactivate policy
```

Full request/response contracts: [docs/ai_architecture.md](docs/ai_architecture.md)

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/ai_architecture.md](docs/ai_architecture.md) | Architecture diagram, provider setup, endpoint contracts, security decisions |
| [docs/ai_permissions_matrix.md](docs/ai_permissions_matrix.md) | RBAC matrix — who can do what, forbidden columns, enforcement layers |
| [docs/ai_eval_results.md](docs/ai_eval_results.md) | Evaluation results — policy, SQL, action, security prompts |

---

## Security

- Forbidden columns (passwords, bank details, PAN, salary, DOB) blocked at two independent layers
- SQL agent: only SELECT allowed; DDL/DML blocked by keyword check before execution
- Action agent: three independent permission checks (LLM hint → `can_perform()` → service function)
- Prompt injection in retrieved policy text: LLM instructed to treat chunks as untrusted content
- All AI interactions logged to `ai_audit_logs` (no secrets in logs)

See [docs/ai_permissions_matrix.md](docs/ai_permissions_matrix.md) for full matrix and refusal examples.

---

## Project Structure

```
hrCopilot/
├── backend/
│   ├── app/
│   │   ├── main.py                      FastAPI app factory
│   │   ├── api/v1/
│   │   │   ├── router.py                API router mount
│   │   │   └── endpoints/
│   │   │       ├── auth.py              Login → JWT
│   │   │       ├── chat.py              All AI chat endpoints + streaming
│   │   │       ├── leaves.py            Leave request + approval REST API
│   │   │       ├── tickets.py           Ticket CRUD
│   │   │       ├── projects.py          Project CRUD
│   │   │       ├── announcements.py     Announcement feed
│   │   │       └── admin.py             Admin CRUD (users, policies, roles)
│   │   ├── core/
│   │   │   ├── config.py                Settings via pydantic BaseSettings (.env)
│   │   │   ├── dependencies.py          get_current_user, require_role, get_db
│   │   │   └── security.py             JWT encode/decode, password hashing
│   │   ├── db/
│   │   │   ├── base.py                  Declarative base
│   │   │   └── session.py               SQLAlchemy session factory
│   │   ├── models/                      SQLAlchemy ORM models
│   │   │   ├── employee.py              Employee + EmployeeRole enum
│   │   │   ├── department.py
│   │   │   ├── project.py
│   │   │   ├── leave.py                 LeaveRequest + LeaveBalance
│   │   │   ├── ticket.py
│   │   │   ├── announcement.py
│   │   │   ├── skill.py
│   │   │   ├── job_history.py
│   │   │   ├── hr_policy.py
│   │   │   ├── policy_group.py
│   │   │   ├── role_category_access.py  Document-level RBAC (role → category)
│   │   │   ├── conversation_memory.py   Per-session AI memory
│   │   │   ├── ai_audit_log.py          AI interaction audit trail
│   │   │   ├── onboarding.py
│   │   │   └── payroll.py
│   │   ├── schemas/                     Pydantic request/response schemas
│   │   │   ├── auth.py
│   │   │   ├── chat.py                  ChatRequest (message, history, confirmed)
│   │   │   ├── common.py                APIResponse wrapper
│   │   │   └── admin.py
│   │   └── services/
│   │       ├── leave_service.py
│   │       ├── ticket_service.py
│   │       ├── project_service.py
│   │       ├── announcement_service.py
│   │       └── ai/
│   │           ├── factory.py           Config-driven provider instantiation
│   │           ├── interfaces/          Abstract base classes
│   │           │   ├── llm.py           LLMProvider ABC
│   │           │   ├── embedder.py      Embedder ABC
│   │           │   └── vector_store.py  VectorStore ABC
│   │           ├── providers/           Concrete implementations (swap via .env)
│   │           │   ├── llm/
│   │           │   │   ├── anthropic.py
│   │           │   │   └── openai_llm.py
│   │           │   ├── embedders/
│   │           │   │   ├── voyage.py
│   │           │   │   └── openai_embedder.py
│   │           │   └── vector_stores/
│   │           │       ├── chroma.py
│   │           │       └── faiss_store.py
│   │           ├── agents/              AI agent implementations
│   │           │   ├── policy_rag.py    RAG pipeline (embed → search → generate)
│   │           │   ├── sql_agent.py     NL→SQL agent with role-filtered schema
│   │           │   ├── action_agent.py  HR task automation + confirmation gate
│   │           │   ├── hr_data_rag.py   HR data RAG (manager/admin)
│   │           │   └── langgraph_agent.py  LangGraph multi-agent orchestration
│   │           ├── routing/             Intent classification + guardrails
│   │           │   ├── router_agent.py  Intent classifier → agent dispatcher
│   │           │   ├── semantic_router.py  Embedding-based semantic routing
│   │           │   ├── intent_routes.py    Route definitions + examples
│   │           │   └── guardrails/
│   │           │       ├── pipeline.py      Guardrail pipeline (preprocess + run)
│   │           │       ├── routes.py        Guardrail route registry
│   │           │       └── middleware/
│   │           │           ├── base.py      GuardrailMiddleware ABC
│   │           │           ├── guardrail.py Jailbreak / injection detection
│   │           │           └── pii.py       PII scrubbing
│   │           └── core/                Cross-cutting AI concerns
│   │               ├── audit.py         log_interaction() — writes ai_audit_logs
│   │               ├── memory/
│   │               │   ├── memory.py    Session memory store/retrieve/summarize
│   │               │   └── context.py   History → prompt block builder
│   │               ├── security/
│   │               │   ├── permissions.py   can_perform(user, action) RBAC gate
│   │               │   └── sql_safety.py    validate_sql, scrub_forbidden_columns
│   │               └── tools/
│   │                   ├── api_tools.py     Service-layer wrappers for action agent
│   │                   └── document_loader.py  Policy file ingestion
│   ├── alembic/                         DB migrations
│   ├── scripts/seed.py                  DB init + data seeding + policy ingestion
│   └── tests/
│       ├── unit/                        Isolated unit tests (no DB/network)
│       │   ├── test_action_agent_parse.py
│       │   ├── test_permissions.py
│       │   ├── test_policy_rag_rbac.py
│       │   ├── test_prompt_injection_defense.py
│       │   ├── test_routing_and_guardrails.py
│       │   ├── test_sql_guardrails.py
│       │   ├── test_hr_data_rag.py
│       │   ├── test_leave_service.py
│       │   ├── test_role_category_access.py
│       │   └── test_chat_history.py
│       └── integration/                 Live API + DB integration tests
│           ├── test_admin_endpoints.py
│           ├── test_chat_endpoints.py
│           ├── test_e2e_workflows.py
│           └── test_live_all_roles.py
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                   Root layout + sidebar nav
│   │   ├── page.tsx                     Redirect → /ai-copilot
│   │   ├── ai-copilot/page.tsx          AI copilot page (mode selector + chat)
│   │   ├── admin/page.tsx               Admin portal (Users / Policies / Access)
│   │   └── login/page.tsx               JWT login form
│   ├── components/ai/
│   │   ├── ChatPanel.tsx                Message input, history, confirmation UI
│   │   ├── ActionResultCard.tsx         HR action result display
│   │   ├── SQLResultTable.tsx           Tabular SQL results
│   │   ├── SourceList.tsx               Policy RAG citations
│   │   ├── Announcements.tsx            Announcement feed
│   │   ├── PendingApprovals.tsx         Manager leave approval panel
│   │   ├── MyLeaves.tsx                 Employee leave history
│   │   ├── MyProjects.tsx               Own project assignments
│   │   └── MyTickets.tsx                Own tickets
│   └── lib/
│       ├── api.ts                       Typed API client (chat, admin, streaming)
│       └── auth.ts                      JWT storage + role decode
├── docs/                                Architecture, permissions matrix, eval results
├── eval/                                Eval dataset + results
├── data/                                Seed data + HR policy markdown files
└── scripts/                             Utility scripts
```
