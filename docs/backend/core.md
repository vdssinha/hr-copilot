# Core Layer — `app/core/`

The core layer provides app-wide configuration, security primitives, and FastAPI dependency injectors. No business logic lives here.

---

## `app/main.py`

Application entry point. Creates the FastAPI instance, registers middleware, mounts the v1 router, and sets up the DB on startup.

### Functions

#### `on_startup() → None`

**Why it exists:** SQLAlchemy does not auto-create tables unless explicitly told to. This startup hook calls `Base.metadata.create_all(bind=engine)` so all ORM models are reflected into SQLite on first boot without needing a migration run in development.

**Behavior:** Runs once when the Uvicorn process starts. Safe to call repeatedly (SQLAlchemy skips tables that already exist).

**Side effect:** Creates all tables defined across `app/models/` if they don't exist.

#### `health() → dict`

**Path:** `GET /health`

**Why it exists:** Load balancers and Docker health checks need a fast no-auth endpoint to verify the process is alive.

**Returns:** `{"status": "ok"}`

---

## `app/core/config.py`

Single source of truth for all configuration. All values are read from environment variables (with `python-dotenv` loading `.env`). Every caller imports named constants from here — no `os.getenv` calls outside this file.

### Constants

#### LLM provider

| Constant | Env var | Default | Purpose |
|---|---|---|---|
| `AI_LLM_PROVIDER` | `AI_LLM_PROVIDER` | `"anthropic"` | Selects `AnthropicProvider` or `OpenAIProvider` in `factory.py` |
| `AI_LLM_MODEL` | `AI_LLM_MODEL` | `"claude-sonnet-4-6"` | Model name passed to the provider |
| `LLM_API_KEY` | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | `""` | Resolved from the selected provider's key env var |
| `LLM_BASE_URL` | `OPENAI_BASE_URL` | `None` | Optional override for OpenAI-compatible local endpoints (e.g., LM Studio) |

#### Embedder

| Constant | Env var | Default | Purpose |
|---|---|---|---|
| `AI_EMBEDDER_PROVIDER` | `AI_EMBEDDER_PROVIDER` | `"voyage"` | Selects `VoyageEmbedder` or `OpenAIEmbedder` |
| `AI_EMBEDDING_MODEL` | `AI_EMBEDDING_MODEL` | `"voyage-3"` | Embedding model name |
| `EMBEDDER_API_KEY` | `VOYAGE_API_KEY` (falls back to `ANTHROPIC_API_KEY`) | `""` | Voyage accepts Anthropic keys as a fallback |

#### Vector store

| Constant | Env var | Default | Purpose |
|---|---|---|---|
| `AI_VECTOR_STORE_PROVIDER` | `AI_VECTOR_STORE_PROVIDER` | `"chroma"` | Selects `ChromaVectorStore` or `FAISSVectorStore` |
| `CHROMA_PERSIST_DIR` | `CHROMA_PERSIST_DIR` | `"./data/chroma_db"` | On-disk path for ChromaDB |

#### Token limits

All AI generation caps are tunable per call site. The file documents the correlation constraints between them (e.g., `POLICY_RAG_ANSWER ≈ 2× SQL_AGENT_QUERY`).

| Constant | Default | Used in |
|---|---|---|
| `AI_MAX_TOKENS_SMART_COPILOT_INTENT` | 512 | `router_agent.classify_intent()` |
| `AI_MAX_TOKENS_SQL_AGENT_QUERY` | 512 | `sql_agent.run_sql_query()` — SQL generation |
| `AI_MAX_TOKENS_SQL_AGENT_SUMMARY` | 256 | `sql_agent.run_sql_query()` — NL summary |
| `AI_MAX_TOKENS_POLICY_RAG_ANSWER` | 1024 | `policy_rag.answer_policy_question()` |
| `AI_MAX_TOKENS_HR_DATA_RAG_ANSWER` | 1024 | `hr_data_rag.query_hr_data()` |
| `AI_MAX_TOKENS_ACTION_AGENT_EXTRACT` | 1024 | `action_agent.run_action()` — intent extraction |
| `AI_MAX_TOKENS_ACTION_AGENT_SUMMARY` | 500 | `action_agent.run_action()` — result summary |

#### Conversation memory

| Constant | Default | Purpose |
|---|---|---|
| `AI_CONTEXT_TURNS` | 3 | Number of prior user+assistant pairs injected into every LLM prompt via `context.build_history_block()` |

---

## `app/core/security.py`

JWT and password hashing utilities. Stateless — no DB access.

### Functions

#### `hash_password(password: str) → str`

Hashes a plain-text password using bcrypt.

**Why bcrypt:** `passlib` with bcrypt is the standard for Python password storage. Salt is embedded in the hash.

**Returns:** bcrypt hash string (e.g., `$2b$12$...`)

**When called:** On user creation (`auth.register`, `admin.create_user`).

---

#### `verify_password(plain: str, hashed: str) → bool`

Verifies a plain-text password against a stored bcrypt hash.

**Returns:** `True` if they match, `False` otherwise.

**When called:** In `auth.login` before issuing a JWT.

---

#### `create_access_token(data: dict, expires_delta: Optional[timedelta] = None) → str`

Creates a signed JWT.

**Parameters:**
- `data` — payload dict; must contain `"sub"` (user ID as string) and optionally `"role"`
- `expires_delta` — override for token lifetime; defaults to `ACCESS_TOKEN_EXPIRE_MINUTES` (480 min = 8 hours)

**Returns:** Signed JWT string.

**Algorithm:** HS256 with `SECRET_KEY` from config.

---

#### `decode_token(token: str) → dict`

Decodes and verifies a JWT. Raises `JWTError` if the token is invalid or expired.

**Returns:** Decoded payload dict (contains `"sub"`, `"role"`, `"exp"`).

**When called:** In `dependencies.get_current_user()` on every protected request.

---

## `app/core/dependencies.py`

FastAPI dependency injectors. Imported via `Depends()` in endpoint signatures.

### Functions

#### `get_current_user(credentials, db) → Employee`

The primary auth guard. Used as `Depends(get_current_user)` on all protected endpoints.

**Flow:**
1. Extracts Bearer token from `Authorization` header via `HTTPBearer`
2. Calls `decode_token(token)` — raises 401 on invalid/expired JWT
3. Queries `employees` WHERE `id = sub AND status = ACTIVE`
4. Returns the `Employee` ORM object

**Raises:**
- `401 Unauthorized` — missing, invalid, or expired token
- `401 Unauthorized` — employee not found or status != ACTIVE

**Parameters:**
- `credentials: HTTPAuthorizationCredentials` — injected by FastAPI from the `Authorization` header
- `db: Session` — injected by `get_db()`

---

#### `require_role(*roles: EmployeeRole) → Callable`

Factory that returns a role-checking dependency.

**Why it's a factory:** Different endpoints need different role sets. `require_role(EmployeeRole.ADMIN)` creates a dependency that 403s non-admins.

**Usage:**
```python
_require_admin = require_role(EmployeeRole.ADMIN)

@router.get("/admin/users")
def list_users(_: Employee = Depends(_require_admin), ...):
    ...
```

**Raises:** `403 Forbidden` if `current_user.role` not in `roles`.

---

## `app/db/session.py`

SQLAlchemy engine and session factory.

### Constants / Objects

#### `engine`

`create_engine(DATABASE_URL, connect_args={"check_same_thread": False})`

`check_same_thread=False` is required for SQLite because FastAPI runs handlers in thread-pool workers — without it, SQLite raises an error when a connection created in one thread is used in another.

#### `SessionLocal`

`sessionmaker(autocommit=False, autoflush=False, bind=engine)`

- `autocommit=False` — explicit `db.commit()` required
- `autoflush=False` — prevents SQLAlchemy from flushing implicitly before queries

### Functions

#### `get_db() → Generator[Session, None, None]`

FastAPI dependency that provides a DB session per request and guarantees it is closed after the response.

**Pattern:**
```python
db = SessionLocal()
try:
    yield db
finally:
    db.close()
```

**Why `yield`:** FastAPI's dependency injection supports generator dependencies. The `finally` block runs after the endpoint handler returns (even on exception), ensuring no connection leaks.

**Usage:** `db: Session = Depends(get_db)` in any endpoint.
