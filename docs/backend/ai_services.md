# AI Services — `app/services/ai/`

---

## `factory.py`

Provider factory. All AI agents call this module — never import providers directly.

### Functions

#### `get_llm_provider() → BaseLLMProvider`

Reads `AI_LLM_PROVIDER` and returns a new provider instance:
- `"anthropic"` → `AnthropicProvider()`
- `"openai"` → `OpenAIProvider()`

**Note:** Creates a new object every call (no caching). Each `AnthropicProvider.__init__` calls `anthropic.Anthropic(api_key=...)`. For production throughput, consider a module-level singleton.

#### `get_embedder() → BaseEmbedder`

Reads `AI_EMBEDDER_PROVIDER`:
- `"voyage"` → `VoyageEmbedder()`
- `"openai"` → `OpenAIEmbedder()`

#### `get_vector_store(collection_name: str = "hr_policies") → BaseVectorStore`

Reads `AI_VECTOR_STORE_PROVIDER`:
- `"chroma"` → `ChromaVectorStore(collection_name)` — opens `PersistentClient` on each call
- `"faiss"` → `FAISSVectorStore(collection_name)` — in-memory; data lost on restart

**Active collections in the system:** `"hr_policies"` (policy RAG), `"hr_data"` (CSV employee data).

---

## `router_agent.py`

Intent classifier and dispatcher. Owns the top-level routing decision for every chat query.

### `classify_intent(message: str) → RouteResult`

**Purpose:** Classify a free-form user message into one of four intents.

**Parameters:**
- `message` — the raw user question

**Returns:** `RouteResult {intent: str, confidence: float, reason: str}`

**Intent values:** `POLICY_QA` | `SQL_QUERY` | `HR_ACTION` | `UNKNOWN`

**How it works:**
1. Calls `get_llm_provider().generate(message, system=_CLASSIFY_SYSTEM, max_tokens=512)`
2. System prompt instructs the LLM to return exactly: `{"intent": "...", "confidence": 0.0-1.0, "reason": "..."}`
3. Strips markdown fences and parses JSON
4. Falls back to regex extraction if JSON is malformed (handles truncated reasoning-model output)
5. Returns `UNKNOWN` if all parsing fails

**Why a separate LLM call for classification:** Routing to the wrong agent is expensive (costs a full RAG or SQL call). The classifier is cheap (512 tokens) and enables targeted prompting per agent.

---

### `route_and_answer(db, user, message, history) → dict`

**Purpose:** Classify intent and call the matching agent. One-stop entry point.

**Parameters:**
- `db` — SQLAlchemy session
- `user` — authenticated `Employee`
- `message` — user question
- `history` — prior conversation turns (list of `{role, content}` dicts)

**Returns:**
```python
{"route": RouteResult, "result": <sub-agent result dict>}
```

**Dispatch table:**

| Intent | Agent called |
|---|---|
| POLICY_QA | `policy_rag.answer_policy_question()` |
| SQL_QUERY | `sql_agent.run_sql_query()` |
| HR_ACTION | `action_agent.run_action()` |
| UNKNOWN | Hardcoded fallback string |

---

## `policy_rag.py`

Retrieval-augmented generation for HR policy questions.

### Module-level constants

| Constant | Value | Purpose |
|---|---|---|
| `_CHUNK_SIZE` | 800 | Max chars per policy text chunk |
| `_CHUNK_OVERLAP` | 100 | Overlap between consecutive chunks to preserve context at boundaries |
| `_RETRIEVAL_K` | 5 | Number of vector search results to fetch |
| `_SIMILARITY_THRESHOLD` | 1.2 | Max cosine distance to accept (0=identical, 2=opposite) |

### Functions

#### `ingest_policies(db: Session) → int`

**Purpose:** Chunk all active HR policies and embed them into the `hr_policies` vector store collection.

**Parameters:** `db` — SQLAlchemy session for reading `HRPolicy` records

**Returns:** Total number of chunks embedded

**Flow:**
1. Load all `HRPolicy` WHERE `is_active=True`
2. Split each policy's `content` with `RecursiveCharacterTextSplitter` (separators: `\n## `, `\n### `, `\n\n`, `\n`, ` `)
3. Build `Document(content=chunk, metadata={policy_id, title, category, filename})` for each chunk
4. Embed in batches of 96 (Voyage API limit)
5. `store.clear()` then `store.add_documents(documents, embeddings)`
6. Mark each policy with `embeddings_generated_at = now()`

**Why clear before add:** Prevents duplicate embeddings if called multiple times. The whole collection is rebuilt from the current DB state.

**Called by:** Background task after policy upload (`admin.upload_policy`), or lazily by `answer_policy_question` if the store is empty.

---

#### `_needs_ingestion(db: Session) → bool`

**Purpose:** Check if lazy ingestion should fire before answering a query.

**Logic:** Returns `True` if ChromaDB collection has zero documents AND there are unembedded active policies in the DB. Prevents re-ingesting if the store already has content.

---

#### `_get_accessible_categories(db, user_role, policy_group) → List[str]`

**Purpose:** Enforce policy RBAC — return only the category names this user is allowed to see.

**Priority:** If `policy_group` is set, look up `GroupCategoryAccess` for that group. If the group has entries, return those. Otherwise fall back to `RoleCategoryAccess` for the user's role.

**Returns:** List of category string values (e.g., `["GENERAL", "BENEFITS"]`)

---

#### `answer_policy_question(db, question, user_role, policy_group, history) → PolicyAnswer`

**Purpose:** Retrieve relevant policy chunks and generate a grounded answer.

**Parameters:**
- `db` — session
- `question` — user question string
- `user_role` — `EmployeeRole` for category filtering
- `policy_group` — optional group name (overrides role-based access)
- `history` — prior conversation turns

**Returns:** `PolicyAnswer {answer: str, sources: List[PolicySource]}`

**Flow:**
1. Lazy ingestion check → `ingest_policies()` if needed
2. `_get_accessible_categories()` → if empty, return "no access" response
3. `embedder.embed_query(question)` — Voyage AI API call
4. `store.similarity_search(embedding, k=5, where={"category": {"$in": accessible}})` — ChromaDB filters by category at query time
5. Filter results by `_SIMILARITY_THRESHOLD` (cosine distance ≤ 1.2)
6. If no relevant chunks: return "not enough information" response
7. Build context block from chunk contents + `build_history_block(history)`
8. `llm.generate(prompt, system=_SYSTEM_PROMPT, max_tokens=1024)`

**Security invariant:** The `where` filter in ChromaDB ensures users only retrieve chunks from categories they can access. An employee with `GENERAL` access cannot retrieve `PAYROLL` policy chunks even if their embedding is semantically close.

---

## `sql_agent.py`

Natural-language to SQL agent with schema-aware generation and layered safety guardrails.

### Module-level constants

`_ALLOWED_TABLES` — 10 tables the LLM may query (excludes sensitive-only tables like `payroll_records`).

`_TABLE_SCHEMAS` — human-readable schema descriptions with sensitive columns pre-excluded from the schema block. The LLM never sees `hashed_password`, `pan_number`, etc. in the schema.

### Functions

#### `_build_access_rules(user: Employee, db: Session) → str`

**Purpose:** Generate a role-specific access constraint string injected into the SQL generation prompt.

**Per-role behavior:**
- `ADMIN / HR / C_LEVEL` — full access to all allowed tables and salary data
- `MANAGER` — public employee fields unrestricted; salary and sensitive employee tables filtered to self + direct reports (`manager_id = user.id`)
- `MARKETING / EMPLOYEE` — all employee-specific tables filtered to `employee_id = user.id`; salary only for own record

**Why in-prompt rules (not post-filter):** The LLM generates the WHERE clause. Injecting the constraint into the prompt is the primary control; `validate_sql` + `scrub_forbidden_columns` are defence-in-depth layers.

---

#### `_extract_sql(raw: str) → Optional[str]`

**Purpose:** Parse the LLM's raw text output into a clean SQL string or a sentinel value.

**Returns:**
- `"ACCESS_DENIED"` sentinel string — if the LLM determined this query is not permitted
- `None` — if the LLM returned `CANNOT_ANSWER` or no valid SQL was found
- SQL string — the first `SELECT ...` block, stripped of markdown fences and trailing semicolons

**Why sentinels:** The LLM can decide access is denied based on the access rules in the prompt. Returning `ACCESS_DENIED` as literal text lets the agent distinguish "no data" from "not allowed".

---

#### `_rows_to_dicts(result) → List[dict]`

Converts a SQLAlchemy `CursorResult` into a list of plain dicts using `result.keys()` as column names.

---

#### `run_sql_query(db, user, question, history) → SQLResult`

**Purpose:** End-to-end NL→SQL pipeline: generate SQL, validate, execute, summarize.

**Parameters:**
- `db` — session
- `user` — authenticated employee (for access rules)
- `question` — user question
- `history` — prior turns

**Returns:** `SQLResult {answer: str, sql: str, rows: List[Any], row_count: int}`

**Flow:**
1. Build schema + access rules → system prompt
2. `llm.generate(prompt, system=system, max_tokens=512)` → raw SQL or sentinel
3. `_extract_sql(raw)` → clean SQL or sentinel
4. `ACCESS_DENIED` → return access-denied response (no DB call)
5. `None` → return "no data" response
6. `validate_sql(sql)` → raises `SQLGuardError` if DDL/DML/forbidden columns/unbalanced parens
7. `db.execute(text(validated_sql))` → SQLite execution
8. `scrub_forbidden_columns(rows)` — remove any sensitive columns that slipped through
9. `llm.generate(summary_prompt, max_tokens=256)` → 1-2 sentence NL summary

**Error handling:** DB execution errors are caught and returned as a safe "could not execute" message. Raw exception text never reaches the caller.

---

## `hr_data_rag.py`

Semantic search over structured employee data from `hr_data.csv`.

### Functions

#### `ingest_hr_data(csv_path: Path) → int`

**Purpose:** Embed one document per CSV row into the `hr_data` vector store collection.

**Format:** Each document is a pipe-separated string of non-empty field values: `"employee_id: E001 | full_name: Alice | department: Engineering | ..."`

**Metadata stored per document:** `source`, `employee_id`, `department`, `manager_id`, `full_name` — used for `where` filtering at query time.

**Returns:** Number of documents embedded (= number of CSV rows).

**Note:** Embeds all columns including sensitive ones (salary, date_of_birth, phone). Access control is enforced at query time by the LLM system prompt — sensitive fields are redacted in the answer for unauthorized roles.

---

#### `query_hr_data(question, user_role, employee_code, employee_name, history) → HRDataAnswer`

**Purpose:** Retrieve relevant employee records via semantic search and generate a role-aware answer.

**Parameters:**
- `question` — user question
- `user_role` — controls search scope and system prompt
- `employee_code` — used for `where` filter for EMPLOYEE/MARKETING roles
- `employee_name` — embedded in system prompt for personalization
- `history` — prior conversation turns

**Returns:** `HRDataAnswer {answer: str, rows_found: int}`

**Access control per role:**

| Role | Search scope | Field access |
|---|---|---|
| ADMIN / HR / C_LEVEL | All records (`k=10`, no filter) | Full access |
| MANAGER | All records | Sensitive fields shown for direct reports (`manager_id == employee_code`), `[RESTRICTED]` for others |
| MARKETING / EMPLOYEE | Own record only (`where={"employee_id": {"$eq": employee_code}}`) | All own fields |

**Security note:** The MANAGER access model relies on the LLM following its system prompt instructions to redact fields. This is a soft control. For harder guarantees, post-processing redaction would be needed.

---

## `action_agent.py`

Extracts structured intent from a natural-language HR request, validates permissions, and dispatches to an in-process tool.

### Functions

#### `_parse_llm_json(raw: str) → dict`

Strips markdown fences, extracts the first `{...}` JSON block, and parses it.

**Why extract first block:** LLMs sometimes emit reasoning text before the JSON. `re.search(r"\{.*\}", raw, re.DOTALL)` isolates just the JSON object.

---

#### `_build_extract_prompt(message, user, history) → str`

Constructs the extraction prompt with:
- Prior conversation (via `build_history_block`)
- User's role
- Sorted list of allowed actions (from `permissions.allowed_actions(user)`)
- The user message

**Why include allowed_actions in the prompt:** The LLM uses this list to detect when the user is asking for something they're not permitted to do, returning a `cannot_do_reason` instead of the action.

---

#### `_summarize_result(llm, action, message, result) → str`

Generates a 1-2 sentence plain-English confirmation after a successful action. Returns the error string directly if `result["success"]` is false (no extra LLM call).

---

#### `run_action(db, user, message, history) → ActionResult`

**Purpose:** Full pipeline: extract intent → check permission → execute tool → summarize.

**Parameters:**
- `db` — session
- `user` — authenticated employee
- `message` — user request (e.g., "apply casual leave from Dec 1 to Dec 3")
- `history` — prior turns

**Returns:** `ActionResult {answer: str, action: str, success: bool, data: Optional[dict]}`

**Flow:**
1. `llm.generate(prompt, system=_EXTRACT_SYSTEM, max_tokens=1024)` → `{action, params, cannot_do_reason}`
2. Parse JSON from response
3. Check `cannot_do_reason` (LLM-reported) and `can_perform(user, action)` (code-level)
4. Dispatch to `api_tools.<action>(db, user, **params)`
5. `_summarize_result(llm, action, message, result)` — second LLM call

**Supported actions:** `apply_leave`, `check_leave_balance`, `approve_leave`, `reject_leave`, `create_ticket`, `assign_ticket`, `create_announcement`, `assign_employee_to_project`

---

## `langgraph_agent.py`

LangGraph state machine wrapping the same agents as `router_agent`. Identical logic, graph-based execution.

### `AgentState` (TypedDict)

Fields: `message`, `db`, `user`, `history` (inputs); `intent`, `confidence`, `reason`, `result`, `error` (mutable).

`db` and `user` are injected at invocation time, not during graph construction.

### Graph structure

```
START → classify → conditional_route →
    policy_rag → END
    sql_agent  → END
    action_agent → END
    unknown    → END
```

### Functions

#### `build_hr_graph() → CompiledGraph`

Constructs and compiles the LangGraph state machine. Called once at module import time.

#### `run_langgraph(db, user, message, history) → dict`

Invokes the compiled graph with an initial state and returns:
```python
{"route": {intent, confidence, reason}, "result": {...}, "error": "..."|None}
```

**Singleton graph:** `_hr_graph = build_hr_graph()` is module-level — the graph is compiled once and reused across all requests.

---

## `context.py`

### `build_history_block(history: list, max_turns: int = AI_CONTEXT_TURNS) → str`

**Purpose:** Format prior conversation turns for injection into LLM prompts.

**Parameters:**
- `history` — list of `{role: str, content: str}` dicts
- `max_turns` — max user+assistant pairs to include (default `AI_CONTEXT_TURNS = 3`)

**Returns:** Formatted string block, or empty string if history is empty.

**Format:**
```
Prior conversation (use only to resolve references like 'her', 'that project' — do NOT re-execute previous queries):
User: <message>
Assistant: <response>
...

Current message:
```

**Why the "do NOT re-execute" instruction:** Without it, models sometimes re-run previous queries when they see historical SQL results in context.

**Token bound:** Trims to `-(max_turns * 2)` messages (last N pairs). At `AI_CONTEXT_TURNS=3`, this is at most 6 messages.

---

## `permissions.py`

Role-based action permission map.

### `_ROLE_PERMISSIONS: dict[EmployeeRole, frozenset[str]]`

Static mapping of role → allowed action names. Defined at module level — no DB involved.

| Permission set | Roles |
|---|---|
| `_EMPLOYEE_BASE` | EMPLOYEE, MARKETING |
| `_EMPLOYEE_BASE + _MANAGER_EXTRA` | MANAGER, HR, C_LEVEL |
| All + `create_project` | ADMIN |

### `can_perform(user: Employee, action: str) → bool`

Returns `True` if `action` is in the user's allowed set.

### `allowed_actions(user: Employee) → frozenset[str]`

Returns the full set of allowed action names for the user's role. Used in `action_agent._build_extract_prompt()` to tell the LLM what the user can do.

---

## `sql_guardrails.py`

SQL safety validator. Runs on every generated SQL before it reaches the DB.

### `_FORBIDDEN_COLUMNS: frozenset`

11 column names that must never appear in any SQL query: `hashed_password`, `bank_account_number`, `bank_account_name`, `bank_branch`, `bank_ifsc`, `pan_number`, `pan_name`, `pan_dob`, `date_of_birth`, `profile_photo_path`, `profile_photo_mime`.

### `_BLOCKED_KEYWORDS: re.Pattern`

Regex matching DDL/DML keywords: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `REPLACE`, `TRUNCATE`, `PRAGMA`, `ATTACH`, `DETACH`.

### `_MAX_ROWS: int = 100`

Hard cap on result rows.

### Functions

#### `validate_sql(sql: str) → str`

**Purpose:** Validate and normalize a SQL string. Returns cleaned SQL or raises `SQLGuardError`.

**Checks (in order):**
1. Strip trailing semicolon
2. Block multi-statement queries (`;` inside the string)
3. Block DDL/DML keywords via `_BLOCKED_KEYWORDS`
4. Must start with `SELECT`
5. Check forbidden column names (word-boundary regex for each)
6. Unbalanced parentheses check (catches truncated LLM output)
7. Inject `LIMIT 100` if missing; cap existing LIMIT at 100

**Raises:** `SQLGuardError(message)` — a subclass of `ValueError` with a user-safe message.

---

#### `scrub_forbidden_columns(rows: list[dict]) → list[dict]`

**Purpose:** Remove forbidden columns from result rows as a defence-in-depth measure after DB execution.

**Why needed:** Even if the SQL validator passes, a `SELECT *` on a table that adds a sensitive column in the future would expose data. This layer always strips forbidden column names from result dicts.

---

#### `_check_forbidden_columns(sql: str) → None`

Internal helper called by `validate_sql`. Uses word-boundary regex (`\b<col>\b`) to avoid false positives on column names that contain a forbidden substring.

---

#### `_enforce_row_limit(sql: str) → str`

Injects `LIMIT 100` if no LIMIT clause exists, or caps any existing LIMIT that exceeds 100 using regex substitution.

---

#### `safe_column_list(columns: Optional[list[str]] = None) → str`

Returns a safe comma-separated column list with forbidden columns removed. Falls back to `"*"` if all columns are forbidden or `columns` is None. Utility for constructing safe SELECT lists programmatically.

---

## `document_loader.py`

Text extraction from uploaded policy files.

### `extract_text(path: Path) → str`

Reads a file from disk and returns its plain text.

**Supported formats:** `.md`, `.txt` (UTF-8 decode), `.pdf` (pypdf page extraction), `.docx` (python-docx paragraph extraction)

**Raises:** `ValueError` for unsupported file types.

---

### `extract_text_bytes(content: bytes, suffix: str, filename: str) → str`

Same as `extract_text` but operates on raw bytes. Used by `admin.upload_policy` which receives file content from the HTTP request body without writing to disk first.

---

## `audit.py`

### `log_ai_interaction(db, user, message, intent, action_status, tool_name, records_accessed) → None`

**Purpose:** Write one `AIAuditLog` row per AI interaction.

**Parameters:**
- `db` — session
- `user` — authenticated employee
- `message` — the original user message
- `intent` — `AIIntent` enum value
- `action_status` — `ActionStatus.SUCCESS | REFUSED | ERROR`
- `tool_name` — string identifying the agent (e.g., `"policy_rag"`, `"sql_agent"`)
- `records_accessed` — optional list serialized as JSON string (policy titles, SQL strings, etc.)

**Called by:** Every chat endpoint handler after the agent returns.

---

## `api_tools.py`

In-process implementations of all actions the action agent can dispatch. These are called directly (not over HTTP). In a distributed system they would be `httpx` calls.

### Leave functions

#### `apply_leave(db, user, leave_type, start_date, end_date, reason, is_half_day, half_day_period) → dict`

Validates dates (ISO format, start ≤ end), parses `LeaveType` and `HalfDayPeriod` enums, inserts a `LeaveRequest` with `status=PENDING`.

**Returns:** `{success: True, data: {id, leave_type, start_date, end_date, status: "PENDING", message}}`

#### `check_leave_balance(db, user, year) → dict`

Returns casual / sick / annual balance totals, used, and remaining for the given year (defaults to current year).

#### `approve_leave(db, actor, request_id) → dict`

Sets `status=APPROVED`, records `approved_by_id` and `approved_at`. Refuses if actor is `EMPLOYEE` role.

#### `reject_leave(db, actor, request_id) → dict`

Same as approve_leave but sets `status=REJECTED`.

### Ticket functions

#### `create_ticket(db, user, title, description, category, priority) → dict`

Creates a `Ticket` with `status=OPEN`. Validates `TicketCategory` and `TicketPriority` enums.

#### `assign_ticket(db, actor, ticket_id, assignee_id, status) → dict`

Sets `assigned_to_id`. Optionally updates ticket status. Refuses for `EMPLOYEE` role.

### Announcement / Project functions

#### `create_announcement(db, actor, title, content, category, is_pinned) → dict`

Creates an `Announcement`. Refuses for `EMPLOYEE` role. Defaults `category` to `GENERAL` on invalid value.

#### `assign_employee_to_project(db, actor, employee_id, project_id, role) → dict`

Creates `EmployeeProject` link. Checks project existence and prevents duplicate active assignments.

---

## Interfaces — `services/ai/interfaces/`

Abstract base classes that all providers must implement.

### `BaseLLMProvider` (llm.py)

```python
def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str: ...
```

`**kwargs` passes `max_tokens` and any future parameters without changing the interface.

---

### `BaseEmbedder` (embedder.py)

```python
def embed(self, texts: List[str]) -> List[List[float]]: ...   # batch embed (for ingestion)
def embed_query(self, text: str) -> List[float]: ...           # single embed (for queries)
```

Two methods because Voyage AI uses different `input_type` for document vs query embedding (affects retrieval quality).

---

### `BaseVectorStore` (vector_store.py)

```python
def add_documents(self, documents: List[Document], embeddings: List[List[float]]) -> None: ...
def similarity_search(self, query_embedding, k, where) -> List[Tuple[Document, float]]: ...
def delete_where(self, where: Dict) -> None: ...
def count(self) -> int: ...
def clear(self) -> None: ...
```

`Document` dataclass: `content: str, metadata: dict`

`similarity_search` returns `(Document, distance_float)` pairs. Distance semantics depend on the provider (cosine distance for Chroma, inner product for FAISS).

`where` filter follows ChromaDB's syntax: `{"key": {"$in": [...]}}` or `{"key": {"$eq": value}}`.

---

## Providers

### `AnthropicProvider` (providers/llm/anthropic.py)

Calls `anthropic.Anthropic.messages.create()` with `model`, `max_tokens`, `system`, and a single user message. Returns `msg.content[0].text`.

### `OpenAIProvider` (providers/llm/openai_llm.py)

Calls `openai.OpenAI.chat.completions.create()`. Handles LM Studio local models that emit chain-of-thought in `reasoning_content` with empty `content` — extracts the last "Draft N:" line or the last non-empty reasoning line as a fallback.

### `VoyageEmbedder` (providers/embedders/voyage.py)

Uses `voyageai.Client.embed()` with `input_type="document"` for batch embed and `input_type="query"` for single query embed. Batch limit: 96 items (enforced in `policy_rag.ingest_policies`).

### `ChromaVectorStore` (providers/vector_stores/chroma.py)

Uses `chromadb.PersistentClient` with `hnsw:space=cosine`. Each instance opens the client and gets/creates the named collection. `clear()` deletes and recreates the collection to fully purge it.

**IDs** are assigned as sequential integers starting from `collection.count()`. This means IDs are never reused after a clear (count resets to 0 after delete+recreate).

### `FAISSVectorStore` (providers/vector_stores/faiss_store.py)

In-memory `IndexFlatIP` (inner product, used with L2-normalized vectors for cosine similarity). No persistence. `where` filter is applied as a post-search Python filter since FAISS has no native metadata filtering. Fetches `k*10` candidates before filtering to improve recall.

**Warning:** `delete_where()` does not rebuild embeddings — it removes documents from `_documents` but leaves the FAISS index stale. Callers must re-ingest after deletion.
