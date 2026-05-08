# Cold-Call Integration Tests

End-to-end tests that hit a **live running backend**. No mocks — real DB, real LLM.

## Prerequisites

- Backend running: `cd backend && uv run --env-file .env uvicorn app.main:app --reload`
- HR data ingested (first run only): `POST /api/v1/chat/hr-data/ingest` as admin
- Policy data ingested (first run only): `POST /api/v1/chat/policy/ingest` as admin

## Run

```bash
# All cold-call tests (default: http://localhost:8000)
cd backend
uv run --env-file .env pytest tests/cold_call/ -v

# Auth tests only (fast, no LLM)
uv run --env-file .env pytest tests/cold_call/test_auth.py -v

# HR RBAC tests (validates field-level access control)
uv run --env-file .env pytest tests/cold_call/test_hr_data_rbac.py -v

# Skip ingest step if already done
COLD_CALL_SKIP_INGEST=1 uv run --env-file .env pytest tests/cold_call/ -v
```

## Override target server

```bash
COLD_CALL_BASE_URL=http://staging:8000 \
COLD_CALL_ADMIN_EMAIL=admin@corp.com \
COLD_CALL_ADMIN_PASS=SecurePass \
pytest tests/cold_call/ -v
```

## Config

All settings are in `config.py` and overridable via env vars:

| Env var                  | Default                         | Purpose                  |
|--------------------------|---------------------------------|--------------------------|
| `COLD_CALL_BASE_URL`     | `http://localhost:8000`         | Backend base URL         |
| `COLD_CALL_ADMIN_EMAIL`  | `priya.sharma@novaworks.in`     | Admin user email         |
| `COLD_CALL_ADMIN_PASS`   | `Admin@1234`                    | Admin password           |
| `COLD_CALL_MGR_EMAIL`    | `arjun.mehta@novaworks.in`      | Manager user email       |
| `COLD_CALL_MGR_PASS`     | `Manager@1234`                  | Manager password         |
| `COLD_CALL_EMP_EMAIL`    | `rahul.verma@novaworks.in`      | Employee user email      |
| `COLD_CALL_EMP_PASS`     | `Employee@1234`                 | Employee password        |
| `COLD_CALL_SKIP_INGEST`  | `0`                             | Set `1` to skip ingest   |

## Test files

| File                    | What it validates                                              |
|-------------------------|----------------------------------------------------------------|
| `test_auth.py`          | Login, token issuance, 401 enforcement                        |
| `test_hr_data_rbac.py`  | Field-level access: employee self-only, manager direct-report restriction, admin unrestricted |
| `test_policy_rag.py`    | Policy RAG: answer quality, source structure, all-role access |
| `test_sql.py`           | SQL generation, DDL/forbidden-column guardrails               |
| `test_actions.py`       | Leave/announcement RBAC, permission enforcement               |
