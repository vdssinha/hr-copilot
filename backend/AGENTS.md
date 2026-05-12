---
last_compiled_date: 2026-05-12
version: 1.1
---

# backend/AGENTS.md

## Purpose

FastAPI + SQLAlchemy backend for CB Nest HRMS with AI copilot feature layer.
Handles all API endpoints, auth/RBAC, AI orchestration, and DB access.

## Entrypoint

`backend/app/main.py` — FastAPI app factory, mounts all routers.

## Key Files

| File | Role |
|------|------|
| `app/core/config.py` | Settings via pydantic BaseSettings; reads from `.env` |
| `app/core/dependencies.py` | `get_current_user()`, `require_role()`, `get_db()` — used in every endpoint |
| `app/core/security.py` | JWT encode/decode, password hashing |
| `app/api/v1/endpoints/chat.py` | All AI chat endpoints (policy/sql/actions/router/hr-data) |
| `app/api/v1/endpoints/leaves.py` | Leave request + approval REST API |
| `app/services/ai/factory.py` | Config-driven provider selection (LLM/embedder/vector store) |
| `app/services/ai/sql_guardrails.py` | Forbidden column enforcement + DDL/DML blocking |
| `app/services/ai/permissions.py` | `can_perform(user, action)` — RBAC gate for AI actions |
| `app/services/ai/audit.py` | `log_interaction()` — writes to `ai_audit_logs` |
| `app/services/ai/policy_rag.py` | RAG pipeline: embed → search → grounded generation |
| `app/services/ai/sql_agent.py` | NL→SQL: role-filtered schema + guardrail validation |
| `app/services/ai/action_agent.py` | HR task automation via intent extraction + service dispatch |
| `app/services/ai/api_tools.py` | Service-layer wrappers called by action_agent |

## AI Provider Plugin Architecture

All AI providers are behind abstract interfaces. Swap via `.env` only:

```
AI_LLM_PROVIDER=openai|anthropic
AI_EMBEDDER_PROVIDER=openai|anthropic
AI_VECTOR_STORE_PROVIDER=chroma|faiss
```

New provider = new file in `services/ai/providers/` + entry in `factory.py`.
No changes to core logic, interfaces, or callers.

## Critical Invariants (DO NOT VIOLATE)

1. **No direct DB writes from AI agents.** Action agent calls `api_tools.py` → service layer → DB.
2. **SQL agent is SELECT-only.** `validate_sql()` blocks DDL/DML. `scrub_forbidden_columns()` is defence-in-depth.
3. **Forbidden columns** must never appear in any SQL agent response:
   `hashed_password`, `bank_account_number`, `bank_account_name`, `bank_branch`, `bank_ifsc`,
   `pan_number`, `pan_name`, `pan_dob`, `date_of_birth`, `current_salary_usd`,
   `profile_photo_path`, `profile_photo_mime`
4. **RBAC in backend.** `require_role()` and `can_perform()` are backend Python checks — never frontend-only.
5. **Audit every AI call.** `log_interaction()` in `finally` block of every chat handler.
6. **No secrets in audit log.** Message and answer_preview only (first 500 chars). No tokens, keys, bank/PAN.

## Working Rules

- New AI provider: implement interface → register in factory.py → test config swap.
- New forbidden column: update BOTH `validate_sql()` AND `scrub_forbidden_columns()` in `sql_guardrails.py`.
- New action tool: add to `api_tools.py` + `permissions.py` + `action_agent.py` dispatch + tests.
- DB schema changes: always create an Alembic migration (`alembic revision --autogenerate`).
- Never `SELECT *` from `employees` — always enumerate safe columns explicitly.

## Validation

```bash
cd backend
pytest tests/unit/test_prompt_injection_defense.py
pytest tests/unit/test_policy_rag_rbac.py
pytest tests/unit/test_action_agent_parse.py
pytest tests/unit/test_hr_data_rag.py
pytest tests/unit/test_leave_service.py
```

## Dev Setup

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY or OPENAI_API_KEY
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```
