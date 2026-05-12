---
schema_version: 1
domain: engineering
system_summary: NovaWorks PeopleOps Copilot — AI feature layer on CB Nest HRMS
topology_hints:
  - backend
  - frontend
  - docs
  - eval
  - data
  - scripts
key_flows:
  - User chat → JWT auth → intent classifier → Policy RAG / SQL Agent / Action Agent → audit log → response
  - Policy ingest → chunk → embed → vector store (ChromaDB/FAISS)
  - HR action → LLM extract intent → service layer function → DB → result
runtime_surfaces:
  - backend/app/main.py
  - frontend/app/ai-copilot/page.tsx
architecture_invariants:
  - AI agents never write directly to the database — all mutations go through service layer
  - SQL agent is read-only — SELECT only, DDL/DML blocked at guardrail level
  - RBAC enforced in backend via JWT — not frontend, not LLM
  - Policy RAG answers are grounded in retrieved docs only — no model memory answers
  - Every AI interaction written to ai_audit_logs — no secrets/bank/PAN in logs
  - All AI providers (LLM, embedder, vector store) swappable via config — zero code change
external_systems:
  - Anthropic Claude API (claude-sonnet-4-6) or OpenAI/LM Studio
  - Voyage AI (embedder, optional)
  - ChromaDB (local vector store, default)
  - FAISS (alternative vector store)
  - SQLite (primary database)
---

# Architecture Overview — NovaWorks PeopleOps Copilot

## System Topology

```
┌──────────────────────────────────────────────────────────────────┐
│                       NEXT.JS FRONTEND                           │
│  /ai-copilot — chat modes:                                       │
│    router | policy | sql | actions | hr-data                     │
│  Components: ChatPanel / SourceList / SQLResultTable /           │
│    ActionResultCard / PendingApprovals / MyLeaves                │
└──────────────────────────┬───────────────────────────────────────┘
                           │ JWT Bearer
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                             │
│  AI Chat: /api/v1/chat/{policy|sql|actions|router|hr-data}       │
│  HR REST: /api/v1/{leaves|tickets|announcements|projects|...}    │
│  Auth:    /api/v1/auth/{login|refresh|me}                        │
│  Admin:   /api/v1/admin/...                                      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
   ┌──────────────────┐      ┌────────────────────────┐
   │   AI Service     │      │   Auth / RBAC          │
   │   Layer          │      │   get_current_user()   │
   │                  │      │   require_role()       │
   │  router_agent    │      │   can_perform()        │
   │  policy_rag      │      └────────────────────────┘
   │  sql_agent       │
   │  action_agent    │
   │  hr_data_rag     │
   │  audit           │
   └────────┬─────────┘
            │
  ┌─────────┼──────────┐
  ▼         ▼          ▼
┌────────┐ ┌────────┐ ┌─────────────┐
│  LLM   │ │Embedder│ │Vector Store │
│Provider│ │Provider│ │  Provider   │
│(iface) │ │(iface) │ │  (iface)    │
└───┬────┘ └───┬────┘ └──────┬──────┘
    │          │             │
OpenAI/   OpenAI/        ChromaDB/
Anthropic  Voyage          FAISS
```

## Key AI Flows

### Policy RAG
```
User question → embed → similarity_search(k=5) → retrieved chunks →
LLM grounded generation → PolicyResult { answer, sources, source_count }
```
Chunking: 800 chars / 100 overlap. Threshold: 1.2 cosine distance.

### SQL Agent
```
User question → schema block + role access rules → LLM generates SELECT →
validate_sql() [block DDL/DML, forbidden columns, inject LIMIT 100] →
execute on SQLite → scrub_forbidden_columns() [defence-in-depth] →
LLM NL summary → SQLResult { answer, sql, rows, row_count }
```

### Action Agent
```
User message → LLM intent extraction → JSON { action, params } →
permission check (can_perform) → dispatch to api_tools →
service layer (same ORM functions as REST endpoints) → DB →
LLM result summary → ActionResult { answer, action, success, data }
```

### Router Agent
```
User message → LLM classify → intent: POLICY_QA | SQL_QUERY | HR_ACTION | UNKNOWN →
delegate to appropriate agent
```

## Plugin / Strategy Pattern

| Config key                 | Default       | Supported values         |
|----------------------------|---------------|--------------------------|
| `AI_LLM_PROVIDER`          | `openai`      | `openai`, `anthropic`    |
| `AI_EMBEDDER_PROVIDER`     | `openai`      | `openai`, `anthropic`    |
| `AI_VECTOR_STORE_PROVIDER` | `chroma`      | `chroma`, `faiss`        |
| `AI_LLM_MODEL`             | `google/gemma-4-31b` | any model ID      |
| `AI_EMBEDDING_MODEL`       | `text-embedding-nomic-embed-text-v1.5` | any  |

`factory.py` reads config and returns concrete provider. Adding a new provider = new file in `providers/` only.

## Security Invariants

1. Forbidden columns blocked at two layers: `sql_guardrails.py` pre-execution + `scrub_forbidden_columns()` post-execution
2. Action agent → service layer → DB only (never raw INSERT/UPDATE/DELETE from agent)
3. RBAC: `can_perform()` runs after JWT decode in Python, never delegated to LLM or frontend
4. Prompt injection: RAG system prompt treats retrieved chunks as untrusted data, not instructions
5. Audit log: captures user_id, role, message, intent, tool_used, action_status — no secrets or PAN/bank data
