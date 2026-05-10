# Pydantic Schemas — `app/schemas/`

Schemas define the request/response shapes validated by FastAPI at the HTTP boundary. They use Pydantic v2.

---

## `common.py`

### `APIResponse`

Unified response envelope returned by all endpoints.

| Field | Type | Notes |
|---|---|---|
| `success` | bool | `True` for ok, `False` for error |
| `data` | Any | Payload — sub-agent result, user object, etc. |
| `error` | Optional[str] | Error message (only set when `success=False`) |

**Factory methods:**
- `APIResponse.ok(data)` → `{success: True, data: data}`
- `APIResponse.fail(error)` → `{success: False, error: error}`

**Why a unified envelope:** Frontend can always check `response.success` before accessing `response.data`, without handling different response shapes per endpoint.

---

## `chat.py`

### `HistoryMessage`

Single conversation turn sent from the frontend.

| Field | Type |
|---|---|
| `role` | `Literal["user", "assistant"]` |
| `content` | str |

### `ChatRequest`

Request body for all `/chat/*` endpoints.

| Field | Type | Default |
|---|---|---|
| `message` | str | required |
| `history` | `List[HistoryMessage]` | `[]` |

History is optional — the frontend sends prior turns to enable reference resolution ("what about her?", "the same project"). Backend trims it to `AI_CONTEXT_TURNS` pairs before injecting into prompts.

---

## `auth.py`

### `LoginRequest`

| Field | Type |
|---|---|
| `email` | str |
| `password` | str |

### `TokenResponse`

Returned by `POST /auth/login`.

| Field | Type | Notes |
|---|---|---|
| `access_token` | str | JWT |
| `token_type` | str | Always `"bearer"` |
| `role` | `EmployeeRole` | For frontend routing (e.g., show admin panel) |
| `user_id` | int | |
| `name` | str | Display name |

### `RegisterRequest`

| Field | Type | Default |
|---|---|---|
| `name` | str | required |
| `email` | str | required |
| `password` | str | required |
| `employee_code` | str | required |
| `role` | `EmployeeRole` | `EMPLOYEE` |

---

## `admin.py`

### User schemas

#### `AdminUserOut`
Safe output schema — excludes `hashed_password` and all sensitive financial fields.

| Field | Type |
|---|---|
| `id`, `employee_code`, `name`, `email` | str/int |
| `role` | EmployeeRole |
| `job_title`, `department_id` | Optional |
| `employment_type` | EmploymentType |
| `status` | EmployeeStatus |
| `joining_date` | Optional[date] |
| `policy_group` | Optional[str] |

`model_config = {"from_attributes": True}` — enables ORM mode for direct SQLAlchemy model serialization.

#### `AdminUserCreate`
Fields for creating a new employee. `password` is plaintext here, hashed in the endpoint handler before storage.

#### `AdminUserUpdate`
All fields optional — supports partial PATCH. `policy_group` can be set to `None` to unassign a group.

### Role / Category schemas

| Schema | Fields | Purpose |
|---|---|---|
| `AdminRoleOut` | `name: str`, `accessible_categories: List[str]` | Read role access |
| `AdminRoleUpdate` | `accessible_categories: List[str]` | Replace role's categories |
| `AdminCategoryOut` | `name: str`, `accessible_by_roles: List[str]` | Read category access |
| `AdminCategoryUpdate` | `accessible_by_roles: List[str]` | Replace category's roles |

### Policy Group schemas

| Schema | Fields |
|---|---|
| `AdminPolicyGroupOut` | `name: str`, `accessible_categories: List[str]` |
| `AdminPolicyGroupCreate` | `name: str`, `accessible_categories: List[str] = []` |
| `AdminPolicyGroupUpdate` | `accessible_categories: List[str]` |

### Policy schemas

#### `AdminPolicyOut`
Output schema for listing policies. Omits `content` (can be very large).

| Field | Notes |
|---|---|
| `id`, `title` | |
| `category` | PolicyCategory enum |
| `filename` | Original upload filename |
| `is_active` | |
| `embeddings_generated_at` | Null = not yet embedded |
| `created_at` | |
