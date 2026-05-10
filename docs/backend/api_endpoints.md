# API Endpoints — `app/api/v1/endpoints/`

All endpoints return `APIResponse` — a unified JSON envelope `{status: "ok"|"error", data: {...}, message: "..."}`.

All protected endpoints require `Authorization: Bearer <jwt>`.

---

## `app/api/v1/router.py`

Mounts three sub-routers under `/api/v1`:

```python
api_router.include_router(auth.router,  prefix="/auth",  tags=["auth"])
api_router.include_router(chat.router,  prefix="/chat",  tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
```

---

## `app/api/v1/endpoints/auth.py`

### `POST /auth/login`

**Purpose:** Authenticate and get a JWT.

**Request body:** `LoginRequest {email: str, password: str}`

**Flow:**
1. Load `Employee` by email
2. `verify_password(payload.password, user.hashed_password)` — bcrypt check
3. Check `user.status == "ACTIVE"`
4. `create_access_token({sub: str(user.id), role: user.role.value})`
5. Return `TokenResponse`

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "access_token": "<jwt>",
    "role": "EMPLOYEE",
    "user_id": 42,
    "name": "Alice Smith"
  }
}
```

**Errors:**
- `401` — wrong email or password
- `403` — account inactive

---

### `POST /auth/register`

**Purpose:** Self-registration (no admin required).

**Request body:** `RegisterRequest {name, email, employee_code, password, role}`

**Flow:**
1. Uniqueness check on email and employee_code
2. `hash_password(payload.password)`
3. Insert `Employee` with `status=ACTIVE` (default)

**Response (200):**
```json
{"status": "ok", "data": {"id": 1, "email": "alice@example.com", "role": "EMPLOYEE"}}
```

**Errors:**
- `400` — email or employee_code already registered

---

## `app/api/v1/endpoints/chat.py`

All chat endpoints accept `ChatRequest {message: str, history: list[{role, content}]}`.

History is passed to all agents via `[h.dict() for h in payload.history]` and trimmed to `AI_CONTEXT_TURNS` pairs inside `context.build_history_block()`.

---

### `POST /chat/policy`

**Purpose:** Answer a question from HR policy documents (RAG).

**Delegates to:** `policy_rag.answer_policy_question(db, message, user_role, policy_group, history)`

**Response:**
```json
{"status": "ok", "data": {"answer": "...", "sources": [{"title": "...", "category": "...", "filename": "..."}]}}
```

**Audit:** Logs `AIIntent.POLICY_QA`. `action_status=REFUSED` if no sources found (answer came from outside policy corpus).

---

### `POST /chat/sql`

**Purpose:** Query structured employee data with natural language.

**Delegates to:** `sql_agent.run_sql_query(db, user, message, history)`

**Response:**
```json
{"status": "ok", "data": {"answer": "...", "sql": "SELECT ...", "rows": [...], "row_count": 5}}
```

**Audit:** Logs `AIIntent.SQL_QUERY`. Stores the generated SQL in `records_accessed`.

---

### `POST /chat/actions`

**Purpose:** Perform HR actions: apply leave, approve leave, create tickets, etc.

**Delegates to:** `action_agent.run_action(db, user, message, history)`

**Response:**
```json
{"status": "ok", "data": {"answer": "Your leave has been submitted.", "action": "apply_leave", "success": true, "data": {...}}}
```

**Audit:** Logs `AIIntent.HR_ACTION`.

---

### `POST /chat/router`

**Purpose:** Auto-classify the intent and dispatch to the right agent. This is the primary endpoint used by the frontend.

**Delegates to:** `router_agent.route_and_answer(db, user, message, history)`

**Response wraps the sub-agent result plus routing metadata:**
```json
{
  "status": "ok",
  "data": {
    "route": {"intent": "POLICY_QA", "confidence": 0.95, "reason": "..."},
    "result": { ...sub-agent response... }
  }
}
```

---

### `POST /chat/router/stream`

**Purpose:** Same as `/chat/router` but streams status events before the final result using NDJSON (one JSON object per line).

**Media type:** `application/x-ndjson`

**Event sequence:**
```
{"type": "status", "message": "Classifying intent…"}
{"type": "status", "message": "Intent: POLICY_QA — ..."}
{"type": "status", "message": "Searching HR policies…"}
{"type": "result", "route": {...}, "result": {...}}
{"type": "done"}
```

**Why streaming:** Reduces perceived latency on the frontend — users see progress before the full answer arrives (LLM calls can take 3-10 seconds).

**Internal function:** `_stream_router(db, user, message, history)` is a Python generator yielded via FastAPI's `StreamingResponse`.

---

### `POST /chat/langgraph`

**Purpose:** Identical logic to `/chat/router` but orchestrated through a LangGraph state machine.

**Delegates to:** `langgraph_agent.run_langgraph(db, user, message, history)`

**When to use:** When you need the graph-based execution model (easier to extend with parallel nodes, retries, or human-in-the-loop steps).

---

### `POST /chat/hr-data`

**Purpose:** Semantic search over the `hr_data.csv` employee data collection.

**Role restrictions enforced inside `hr_data_rag.query_hr_data()`:**
- EMPLOYEE / MARKETING: filtered to own record only
- MANAGER: all records; LLM instructed to redact sensitive fields for non-direct-reports
- ADMIN / HR / C_LEVEL: full access

**Response:**
```json
{"status": "ok", "data": {"answer": "...", "rows_found": 3}}
```

---

### `POST /chat/policy/ingest`

**Purpose:** Admin-only trigger to re-embed all active policies into ChromaDB.

**Auth:** Requires `EmployeeRole.ADMIN` (checked inside handler, not via `require_role` dependency).

**Response:**
```json
{"status": "ok", "data": {"chunks_ingested": 47}}
```

---

## `app/api/v1/endpoints/admin.py`

All admin endpoints require `EmployeeRole.ADMIN` via `_require_admin = require_role(EmployeeRole.ADMIN)`.

---

### User CRUD

#### `GET /admin/users`
Returns all employees ordered by name. Returns full `AdminUserOut` schema.

#### `POST /admin/users`
Creates a new employee. Checks email + employee_code uniqueness. Hashes password. Returns `AdminUserOut` with `201`.

#### `PATCH /admin/users/{user_id}`
Partial update. Prevents admins from editing their own account. If `policy_group` is set, validates it exists in `policy_groups` table.

#### `DELETE /admin/users/{user_id}`
Cascading delete: removes AI audit logs, leave requests and balances, project/skill assignments, job history, onboarding tasks, payroll records, announcements, tickets (created). Nullifies `assigned_to_id` on tickets and `manager_id` on reports before deleting the employee.

**Why cascade in code, not DB:** SQLite foreign key support is inconsistent across versions. Explicit deletion order ensures referential integrity.

---

### Role & Category Access

#### `GET /admin/roles`
Returns each `EmployeeRole` with its list of accessible `PolicyCategory` values.

#### `PATCH /admin/roles/{role_name}`
Replaces all `RoleCategoryAccess` rows for this role. Validates all categories exist as `PolicyCategory` enum values.

#### `GET /admin/categories`
Returns each `PolicyCategory` with the roles that can access it (inverse of roles view).

#### `PATCH /admin/categories/{category_name}`
Replaces all `RoleCategoryAccess` rows for this category.

---

### Policy Management

#### `GET /admin/policies`
Returns all `HRPolicy` records ordered by creation date descending.

#### `POST /admin/policies/upload` (multipart/form-data)

**Parameters:** `title` (form), `category` (form), `file` (file upload)

**Allowed file types:** `.md`, `.txt`, `.pdf`, `.docx`

**Flow:**
1. Validate `category` as `PolicyCategory` enum
2. Validate file extension
3. `extract_text_bytes(content, suffix)` → plain text
4. Save file to `POLICY_UPLOAD_DIR/<category>/<filename>`
5. Insert `HRPolicy` record
6. Queue `ingest_policies(db)` as a `BackgroundTask` (non-blocking — response returns before embedding completes)

**Response:** `{"policy_id": 5, "status": "ingestion_queued"}`

#### `DELETE /admin/policies/{policy_id}`
Deletes vector store chunks (`store.delete_where({"policy_id": id})`) before deleting the DB row, keeping ChromaDB in sync.

---

### Policy Groups

Policy groups allow fine-grained category access overrides beyond role defaults. An employee assigned to a group uses the group's categories instead of their role's.

#### `GET /admin/policy-groups`
#### `POST /admin/policy-groups`
Creates a new named group (name is normalized: lowercased, spaces → underscores).

#### `PATCH /admin/policy-groups/{group_name}`
Replaces the group's category access list.

#### `DELETE /admin/policy-groups/{group_name}`
Deletes the group and its category mappings. Nullifies `policy_group` on all employees who were in this group.

---

### HR Data Ingestion

#### `POST /admin/hr-data/ingest`
Queues `ingest_hr_data(csv_path)` as a background task against `data/employees/hr_data.csv`.

**Response:** `{"status": "ingestion_queued", "file": "..."}`
