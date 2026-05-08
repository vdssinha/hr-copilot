---
generated: 2026-05-08
governance: balanced
---

# AI Readiness Report — hrCopilot

## Score: 35 / 100

Greenfield project. Foundation artifacts complete. No implementation yet.

---

## Verified ✅

| Artifact | Signal |
|----------|--------|
| `AGENTS.md` | Complete — invariants, module map, RBAC matrix, endpoint contracts |
| `CLAUDE.md` | Complete — working style, dev workflow rules, plugin architecture mandate |
| `backend/requirements.txt` | All deps pinned — FastAPI, SQLAlchemy, Alembic, Anthropic, LangChain, ChromaDB |
| `backend/.env.example` | All env vars documented — provider selection, keys, JWT, DB, ChromaDB |
| `service.md` | Service pack bootstrapped — non-negotiables, critical paths, boundaries |

## Missing / Draft 🔴

| Artifact | Gap |
|----------|-----|
| Backend app code | None — no `app/` directory, no models, no endpoints |
| Database migrations | None — no Alembic versions |
| Seed data | None — no HR policies, employees, departments |
| AI modules | None — no policy_rag, sql_agent, action_agent |
| Frontend | None — no Next.js app |
| `docs/ai_architecture.md` | Empty docs/ directory |
| `docs/ai_permissions_matrix.md` | Missing |
| `docs/ai_eval_results.md` | Missing |
| Test suite | None |
| `scripts/seed.py` | Missing |

---

## Recommended Next Actions (Ordered)

### Milestone 1 — DB Models + Migrations
Build all SQLAlchemy ORM models for HRMS tables + Alembic migrations + seed script.
Tables: `employees`, `departments`, `projects`, `employee_projects`, `skills`, `employee_skills`, `job_history`, `leave_requests`, `leave_balances`, `tickets`, `onboarding_tasks`, `announcements`, `payroll_records`, `hr_policies`, `ai_audit_logs`.

### Milestone 2 — Auth + RBAC Layer
JWT auth endpoints (`POST /api/v1/auth/login`, `POST /api/v1/auth/register`), role middleware, `get_current_user` dependency injected into every protected route.

### Milestone 3 — Policy RAG Module
ChromaDB ingestion pipeline, chunking, embedding, retrieval, grounded answer generation via Claude.
Endpoint: `POST /api/v1/chat/policy`.

### Milestone 4 — SQL Agent Module
Schema-aware NL→SQL, guardrail validator, forbidden-column scrubber, role-filtered execution.
Endpoint: `POST /api/v1/chat/sql`.

### Milestone 5 — Action Agent + Chat Router
HR task automation via backend API tool calling, unified router.
Endpoints: `POST /api/v1/chat/actions`, `POST /api/v1/chat/router`.

### Milestone 6 — Frontend
Next.js AI copilot page with chat panel, source list, SQL result table, action card.

### Milestone 7 — Docs + Eval
`docs/ai_architecture.md`, permissions matrix, eval dataset, README updates.

---

## Automatic Failure Risks to Watch

- Agent direct DB write — **auto-fail**
- SQL agent returns forbidden columns — **auto-fail**
- Auth enforced frontend-only — **auto-fail**
- API keys committed — **auto-fail**
- Existing HRMS features broken — **auto-fail**
