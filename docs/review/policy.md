---
schema_version: 1
domain: delivery
review_heuristics:
  - reject any change that allows direct DB writes from AI agent code
  - reject any weakening of sql_guardrails.py validate_sql() or scrub_forbidden_columns()
  - reject missing can_perform() check before action dispatch
  - reject forbidden column exposure in SQL agent responses
  - reject API keys or secrets committed to version control
  - reject RBAC moved from backend to frontend-only
  - require AGENTS.md update when module contracts change
  - require one concern per commit
mandatory_reviewers:
  - vijaydeep
---

# Review Policy — NovaWorks PeopleOps Copilot

## Review Owner

vijaydeep

## Scope

All changes to `backend/` and `frontend/`. Special scrutiny for:
- `backend/app/services/ai/` (AI service layer)
- `backend/app/services/ai/sql_guardrails.py` (security critical)
- `backend/app/services/ai/permissions.py` (security critical)
- `backend/app/core/dependencies.py` (auth critical)

## Hard Gates (Auto-Reject)

Any change that:
- Allows AI agent to write directly to the database (INSERT/UPDATE/DELETE from agent code)
- Removes or weakens `validate_sql()` or `scrub_forbidden_columns()` in `sql_guardrails.py`
- Removes `can_perform()` check before any action dispatch
- Exposes forbidden columns (`hashed_password`, `bank_account_*`, `pan_*`, `date_of_birth`, `current_salary_usd`)
- Commits API keys or secrets to version control
- Moves RBAC checks from backend to frontend-only
- Breaks existing HRMS features (leaves, tickets, announcements, projects)

## AI Service Changes

For changes to `services/ai/`:
- New provider: confirm it implements the abstract interface + config-driven only
- New action tool: confirm permission check in `permissions.py` + service-layer dispatch + no raw SQL write
- New forbidden column: confirm blocked in BOTH `validate_sql()` AND `scrub_forbidden_columns()`
- RAG changes: confirm grounding system prompt is preserved

## Commit Granularity

One concern per commit. Examples:
- `feat(ai): add new LLM provider`
- `fix(sql): add forbidden column to guardrail`
- `feat(action): add approve_ticket action tool`

Do not bundle multiple AI concerns in one commit.

## Pre-Merge Checklist

- [ ] `pytest tests/unit/` passes
- [ ] Security test cases pass 100%
- [ ] No API keys or `.env` files committed
- [ ] AGENTS.md updated if module contracts changed
- [ ] Existing HRMS features not broken (manual smoke test: login, leave apply, ticket create)
