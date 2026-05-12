---
schema_version: 1
domain: delivery
quality_gates:
  - all security tests pass (100%) before any merge
  - forbidden column blocking: 100% pass rate
  - SQL DDL/DML blocking: 100% pass rate
  - RBAC enforcement: 100% pass rate
  - pytest unit tests pass with no failures
test_taxonomy:
  - unit: backend service layer and AI module logic
  - security: forbidden columns, DDL blocking, RBAC, prompt injection
  - eval: AI quality eval dataset (policy RAG, SQL agent, action agent)
  - smoke: login, leave apply, ticket create, policy question (manual)
---

# Testing Strategy — NovaWorks PeopleOps Copilot

## Philosophy

Security and correctness tests are mandatory and must pass 100%.
AI quality tests (RAG grounding, SQL accuracy) use pass-rate thresholds.
Unit tests for service layer run without live API keys (mock providers).

## Test Taxonomy

### Unit Tests (`backend/tests/unit/`)

| File | What it covers |
|------|---------------|
| `test_policy_rag_rbac.py` | Policy RAG role filtering, source citation correctness |
| `test_action_agent_parse.py` | LLM JSON parse, intent extraction, permission gate |
| `test_prompt_injection_defense.py` | Malicious content in retrieved policy docs is not followed |
| `test_hr_data_rag.py` | HR data semantic search correctness |
| `test_leave_service.py` | Leave service business logic (balance, approval rules) |

### Security Tests (must pass 100%)

Run as part of unit tests. Key scenarios:

- SQL agent rejects `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/PRAGMA/ATTACH/DETACH`
- SQL agent output never contains `hashed_password`, `bank_account_number`, `bank_account_name`,
  `bank_branch`, `bank_ifsc`, `pan_number`, `pan_name`, `pan_dob`, `date_of_birth`,
  `current_salary_usd`, `profile_photo_path`, `profile_photo_mime`
- Employee cannot approve leave, assign projects, or create announcements via action agent
- Prompt injection in policy content does not change agent behavior
- Cross-user data access blocked for EMPLOYEE role

### AI Eval (`eval/dataset.json`)

Covers 203 test cases across Policy RAG, SQL Agent, Action Agent, Security, RBAC.
Run: `python scripts/run_eval.py --dataset ../eval/dataset.json`
Target: 100% security tests pass; ≥90% overall pass rate.

## Coverage Targets

| Area | Target |
|------|--------|
| Security / forbidden column blocking | 100% |
| SQL DDL/DML blocking | 100% |
| RBAC permission enforcement | 100% |
| Policy RAG grounded answers | ≥90% |
| Action agent intent extraction | ≥85% |

## Running Tests

```bash
cd backend
pytest tests/unit/ -v

# Full eval
python scripts/run_eval.py --dataset ../eval/dataset.json
```

## What NOT to Test

- Don't mock SQLite for unit tests of the SQL agent — use a test DB with seed data.
- Don't test LLM output quality with hardcoded expected strings — use semantic pass/fail criteria.
- Don't test frontend authorization — all auth is backend. Frontend role display is cosmetic.
