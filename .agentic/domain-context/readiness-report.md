---
generated: 2026-05-08
governance: balanced
---

# AI Readiness Report — hrCopilot

## Score: 85 / 100

Full implementation complete. All minimum passing requirements met. Test suite absent.

---

## Verified ✅

| Artifact | Signal |
|----------|--------|
| `AGENTS.md` | Complete — invariants, module map, RBAC matrix, endpoint contracts |
| `CLAUDE.md` | Complete — working style, dev workflow rules, plugin architecture mandate |
| `README.md` | Setup guide, provider configs, project layout, security overview |
| `backend/requirements.txt` | All deps pinned — FastAPI, SQLAlchemy, Alembic, Anthropic, ChromaDB |
| `backend/.env.example` | All env vars documented — provider selection, keys, JWT, DB, ChromaDB |
| `backend/app/core/config.py` | Pydantic Settings — all AI provider keys, model selection, JWT, DB URL |
| `backend/app/models/` | 12 models — employees, departments, projects, skills, leaves, tickets, announcements, hr_policy, payroll, onboarding, job_history, ai_audit_log |
| `backend/app/services/ai/interfaces/` | Abstract base classes for LLM, Embedder, VectorStore |
| `backend/app/services/ai/providers/` | OpenAI + Anthropic LLMs; OpenAI + Voyage embedders; ChromaDB + FAISS vector stores |
| `backend/app/services/ai/factory.py` | Config-driven provider factory — all 6 providers covered |
| `backend/app/services/ai/policy_rag.py` | Chunking, embedding, retrieval (k=5, threshold 1.2), grounded generation, prompt injection defence |
| `backend/app/services/ai/sql_agent.py` | NL→SQL with role-filtered access rules, enum values in schema, NL summarization |
| `backend/app/services/ai/sql_guardrails.py` | DDL/DML block, SELECT-only, 12 forbidden columns, unbalanced parens, LIMIT 100 |
| `backend/app/services/ai/action_agent.py` | JSON intent extraction (regex fallback), permission check, dispatch, summarization |
| `backend/app/services/ai/api_tools.py` | 8 HR action tools — all enforce RBAC, all go via service layer |
| `backend/app/services/ai/permissions.py` | RBAC permission table — EMPLOYEE/MANAGER/ADMIN action sets |
| `backend/app/services/ai/router_agent.py` | Intent classifier → POLICY_QA/SQL_QUERY/HR_ACTION/UNKNOWN |
| `backend/app/services/ai/audit.py` | Logs all AI interactions; no secrets in log fields |
| `backend/app/api/v1/endpoints/chat.py` | 5 endpoints — all auth-gated; all audit-logged |
| `backend/alembic/versions/001_initial_schema.py` | Initial schema migration |
| `backend/scripts/seed.py` | 8 employees, 3 depts, 15 skills, 3 projects, 5 HR policies, leave balances, tickets, announcements |
| `backend/data/policies/` | 5 HR policy markdown files (leave, WFH, attendance, code of conduct, benefits) |
| `frontend/app/ai-copilot/page.tsx` | 4-mode chat UI (router, policy, sql, actions) |
| `frontend/components/ai/ChatPanel.tsx` | Chat panel with message history, loading state, error display |
| `frontend/components/ai/SourceList.tsx` | Policy source citations |
| `frontend/components/ai/SQLResultTable.tsx` | SQL result table + SQL display toggle |
| `frontend/components/ai/ActionResultCard.tsx` | Action success/failure card |
| `frontend/lib/api.ts` | Typed API client — all 4 chat endpoints with JWT headers |
| `docs/ai_architecture.md` | System diagram, provider setup, endpoint contracts, security decisions |
| `docs/ai_permissions_matrix.md` | Full RBAC matrix, forbidden columns, 3-layer enforcement, refusal table |
| `docs/ai_eval_results.md` | Real eval results (5/5 policy, 5/5 SQL, 3/3 action, 5/5 security) |
| `service.md` | Non-negotiables, critical paths, boundaries, plugin architecture |

---

## Non-Negotiables Status

| Rule | Status |
|------|--------|
| No direct DB writes from AI agents | ✅ — api_tools.py goes via service layer, no raw SQL |
| SQL agent SELECT-only | ✅ — DDL/DML keyword block + SELECT regex in validate_sql() |
| 12 forbidden columns blocked | ✅ — pre-execution guardrail + post-execution row scrub |
| RBAC enforced backend-side | ✅ — JWT decode on every endpoint; 3 independent action checks |
| Policy RAG grounded only | ✅ — system prompt + threshold filter; prompt injection defence |
| Audit logs never log secrets | ✅ — audit.py logs user_id, role, intent, tool, status only |
| All AI infra behind abstract interfaces | ✅ — 3 abstractions, 6 provider implementations, factory pattern |
| No API keys committed | ✅ — config.py defaults are empty strings; .env not committed |

---

## Missing / Incomplete 🔴

| Artifact | Gap |
|----------|-----|
| Test suite | No unit or integration tests — `pytest` not used anywhere |
| Streaming responses | Synchronous only — SSE/WebSocket not implemented |
| Anthropic embedder provider | `providers/embedders/anthropic.py` maps to Voyage AI (not native Claude embeddings) — correct but naming could confuse |

---

## Score Breakdown

| Domain | Weight | Score | Notes |
|--------|--------|-------|-------|
| Foundation (AGENTS.md, service.md, config, .env.example) | 20 | 20/20 | All artifacts complete and accurate |
| AI modules (RAG, SQL, action, router, guardrails, audit) | 35 | 35/35 | All 4 features + guardrails + audit fully implemented |
| Plugin/strategy architecture | 10 | 10/10 | 3 abstractions, 6 providers, factory |
| Frontend integration | 10 | 10/10 | 5 components, typed API client, all endpoints wired |
| Documentation | 10 | 10/10 | Architecture, permissions matrix, eval results, README |
| Test suite | 10 | 0/10 | No tests written |
| Bonus / production readiness | 5 | 0/5 | No streaming, no LangGraph, no eval dataset JSON |

**Total: 85 / 100**

---

## Automatic Failure Risk Assessment

| Risk | Status |
|------|--------|
| Agent direct DB write | ✅ Not present |
| SQL agent returns forbidden columns | ✅ Blocked (2 layers) |
| Auth enforced frontend-only | ✅ Not the case — all checks server-side |
| API keys committed | ✅ Not present |
| Existing HRMS features broken | ✅ AI endpoints are additive-only |

---

## Recommended Next Actions

### High Priority
1. **Add test suite** — pytest unit tests for `sql_guardrails.py` (validate_sql, scrub), `permissions.py` (can_perform), and `policy_rag.py` (threshold behaviour). Integration tests for `/api/v1/chat/` endpoints with seeded DB.

### Low Priority (Bonus)
2. **Streaming** — SSE from `/chat/router` for progressive rendering ("Classifying intent… Retrieving policy…").
3. **Eval dataset JSON** — formalise `docs/ai_eval_results.md` as a machine-readable `eval/dataset.json` with expected_route and expected_behavior fields.
