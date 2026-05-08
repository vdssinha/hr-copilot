# NovaWorks PeopleOps Copilot

AI-powered HR operations assistant built on top of the CB Nest HRMS platform.  
DS Bootcamp assignment — full-stack AI feature integration.

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
- Node.js 18+
- One of: Anthropic API key, OpenAI API key, or LM Studio running locally

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your provider settings (see below)

python scripts/seed.py          # initialise DB + seed HR data + ingest policies
uvicorn app.main:app --reload   # starts on http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                     # starts on http://localhost:3000
```

Navigate to `http://localhost:3000/ai-copilot` and log in with a seeded account:

| Email | Password | Role |
|-------|----------|------|
| rahul.verma@novaworks.in | password123 | EMPLOYEE |
| arjun.mehta@novaworks.in | password123 | MANAGER |
| priya.sharma@novaworks.in | password123 | ADMIN |

---

## LM Studio Setup (local inference)

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

## Anthropic + Voyage Setup

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
POST /api/v1/auth/login          login → JWT
POST /api/v1/chat/policy         Policy RAG
POST /api/v1/chat/sql            SQL Agent
POST /api/v1/chat/actions        HR Action Agent
POST /api/v1/chat/router         Unified router (auto-classify)
POST /api/v1/chat/policy/ingest  Re-index policies (admin only)
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
│   │   ├── api/v1/endpoints/        FastAPI routers
│   │   ├── core/                    Config, JWT, dependencies
│   │   ├── db/                      Session, base
│   │   ├── models/                  SQLAlchemy models (11 tables + audit log)
│   │   ├── schemas/                 Pydantic schemas
│   │   └── services/ai/
│   │       ├── interfaces/          Abstract base classes (LLM, Embedder, VectorStore)
│   │       ├── providers/           Concrete implementations (OpenAI, Anthropic, Chroma, FAISS)
│   │       ├── factory.py           Config-driven provider instantiation
│   │       ├── policy_rag.py        RAG pipeline
│   │       ├── sql_agent.py         NL→SQL agent
│   │       ├── sql_guardrails.py    SQL safety layer
│   │       ├── action_agent.py      HR task automation
│   │       ├── api_tools.py         Backend API tool implementations
│   │       ├── permissions.py       RBAC action permissions
│   │       ├── router_agent.py      Intent classifier + router
│   │       └── audit.py             AI audit logging
│   ├── data/policies/               HR policy markdown files
│   ├── scripts/seed.py              DB initialisation + data seeding
│   └── .env.example                 Environment variable reference
├── frontend/
│   ├── app/ai-copilot/              AI copilot page
│   ├── components/ai/               Chat panel, source list, SQL table, action card
│   └── lib/api.ts                   Typed API client
└── docs/                            Architecture, permissions, eval results
```
