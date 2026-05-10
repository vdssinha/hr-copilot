# Backend Documentation Index

| File | Covers |
|---|---|
| [OVERVIEW.md](OVERVIEW.md) | Architecture, request lifecycle, RBAC, provider plugin system, endpoint summary, design invariants |
| [core.md](core.md) | `app/main.py`, `core/config.py`, `core/security.py`, `core/dependencies.py`, `db/session.py` |
| [api_endpoints.md](api_endpoints.md) | All `/auth/*`, `/chat/*`, `/admin/*` endpoints — request/response, flow, errors |
| [ai_services.md](ai_services.md) | `factory.py`, `router_agent.py`, `policy_rag.py`, `sql_agent.py`, `hr_data_rag.py`, `action_agent.py`, `langgraph_agent.py`, `context.py`, `permissions.py`, `sql_guardrails.py`, `document_loader.py`, `audit.py`, `api_tools.py`, all interfaces and providers |
| [models.md](models.md) | All SQLAlchemy ORM models — columns, enums, relationships |
| [schemas.md](schemas.md) | All Pydantic request/response schemas |

## Where to start

- **Understand the system end-to-end** → [OVERVIEW.md](OVERVIEW.md)
- **Add a new API endpoint** → [api_endpoints.md](api_endpoints.md) + [schemas.md](schemas.md)
- **Add a new AI provider (LLM/embedder/vector store)** → [ai_services.md](ai_services.md) — Interfaces + Providers section
- **Add a new action the bot can perform** → [ai_services.md](ai_services.md) — `action_agent.py` + `api_tools.py` + `permissions.py`
- **Understand the RBAC model** → [OVERVIEW.md](OVERVIEW.md) RBAC section + [models.md](models.md) `role_category_access` / `policy_group`
- **Understand what's in the DB** → [models.md](models.md)
- **Debug a slow query** → [OVERVIEW.md](OVERVIEW.md) Request Lifecycle section — identifies all external API calls per query type
