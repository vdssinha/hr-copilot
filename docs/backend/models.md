# Database Models — `app/models/`

All models inherit from `app.db.base.Base` (SQLAlchemy declarative base). SQLite is the backing store. All tables are created by `Base.metadata.create_all()` on startup.

---

## `employee.py`

Core entity. All other models reference `employees` via foreign keys.

### Enums

| Enum | Values | Purpose |
|---|---|---|
| `EmployeeRole` | EMPLOYEE, MANAGER, ADMIN, HR, MARKETING, C_LEVEL | Controls RBAC in all agents and admin endpoints |
| `EmploymentType` | FULL_TIME, PART_TIME, CONTRACT | Employment classification |
| `EmployeeStatus` | ACTIVE, INACTIVE, NOTICE, TERMINATED | Gate for login — only ACTIVE users can authenticate |

### `Employee` table: `employees`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Internal ID, used in JWTs (`sub`) |
| `employee_code` | String(20) unique | Business ID (e.g., `EMP001`) |
| `name` | String(200) | Display name |
| `email` | String(200) unique index | Login identifier |
| `hashed_password` | String(255) | bcrypt hash — never exposed via SQL agent |
| `role` | Enum(EmployeeRole) | Drives all permission checks |
| `department_id` | FK→departments | Optional department assignment |
| `manager_id` | FK→employees | Self-referential; used by SQL agent for direct-report filtering |
| `job_title` | String(200) | Optional |
| `employment_type` | Enum(EmploymentType) | |
| `status` | Enum(EmployeeStatus) | Must be ACTIVE to log in |
| `joining_date` | Date | Optional |
| `date_of_birth` | Date | Sensitive — in `_FORBIDDEN_COLUMNS` |
| `current_salary_usd` | Float | Sensitive — role-restricted in SQL agent |
| `bank_account_number` | String(50) | Sensitive — in `_FORBIDDEN_COLUMNS` |
| `bank_account_name` | String(200) | Sensitive |
| `bank_branch` | String(200) | Sensitive |
| `bank_ifsc` | String(20) | Sensitive |
| `pan_number` | String(20) | Sensitive |
| `pan_name` | String(200) | Sensitive |
| `pan_dob` | Date | Sensitive |
| `profile_photo_path` | String(500) | Sensitive |
| `profile_photo_mime` | String(50) | Sensitive |
| `policy_group` | String(100) | Optional group name — overrides role-based policy category access |
| `created_at`, `updated_at` | DateTime | Audit timestamps |

### Relationships

- `department` → `Department` (via `department_id`)
- `headed_department` → `Department` (via `Department.head_id`) — departments this employee heads
- `manager` → `Employee` (self-referential) — this employee's manager
- `reports` → `List[Employee]` — direct reports
- All HR entities (projects, skills, job_history, leave_requests, leave_balances, tickets_created, tickets_assigned, announcements, onboarding_tasks, payroll_records, ai_audit_logs)

---

## `hr_policy.py`

### Enums

| Enum | Values |
|---|---|
| `PolicyCategory` | LEAVE, ATTENDANCE, CODE_OF_CONDUCT, BENEFITS, COMPENSATION, IT, GENERAL |

### `HRPolicy` table: `hr_policies`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `title` | String(300) unique | Policy document title |
| `content` | Text | Full extracted text — what gets chunked and embedded |
| `category` | Enum(PolicyCategory) | Used for RBAC filtering in vector store queries |
| `filename` | String(300) | Original uploaded filename, stored for reference |
| `is_active` | Boolean | Only active policies are embedded and returned |
| `created_by_id` | FK→employees | Admin who uploaded |
| `embeddings_generated_at` | DateTime | Null if not yet embedded; set by `ingest_policies()` |
| `created_at`, `updated_at` | DateTime | |

---

## `leave.py`

### Enums

| Enum | Values |
|---|---|
| `LeaveType` | CASUAL, SICK, ANNUAL, UNPAID |
| `HalfDayPeriod` | MORNING, AFTERNOON |
| `LeaveStatus` | PENDING, APPROVED, REJECTED, CANCELLED |

### `LeaveBalance` table: `leave_balances`

One row per employee per year. Stores total and used days for each leave type. Remaining = total - used.

| Column | Type | Default |
|---|---|---|
| `employee_id` | FK→employees | |
| `year` | Integer | |
| `casual_leave_total` | Float | 12.0 |
| `casual_leave_used` | Float | 0.0 |
| `sick_leave_total` | Float | 12.0 |
| ... | | |
| `annual_leave_total` | Float | 15.0 |

### `LeaveRequest` table: `leave_requests`

One row per leave application.

| Column | Type | Notes |
|---|---|---|
| `employee_id` | FK→employees | Who applied |
| `leave_type` | Enum(LeaveType) | |
| `start_date`, `end_date` | Date | Inclusive range |
| `is_half_day` | Boolean | If true, only half a day is taken |
| `half_day_period` | Enum(HalfDayPeriod) | MORNING or AFTERNOON (nullable) |
| `reason` | Text | Optional |
| `status` | Enum(LeaveStatus) | Starts PENDING |
| `approved_by_id` | FK→employees | Set on approval/rejection |
| `approved_at` | DateTime | Set on approval/rejection |

---

## `ticket.py`

### Enums

| Enum | Values |
|---|---|
| `TicketCategory` | IT, HR, FACILITIES, FINANCE, OTHER |
| `TicketPriority` | LOW, MEDIUM, HIGH, CRITICAL |
| `TicketStatus` | OPEN, IN_PROGRESS, RESOLVED, CLOSED |

### `Ticket` table: `tickets`

| Column | Notes |
|---|---|
| `created_by_id` | FK→employees — who raised it |
| `assigned_to_id` | FK→employees nullable — who is handling it |
| `resolved_at` | DateTime nullable |

---

## `announcement.py`

### Enum: `AnnouncementCategory`
Values: GENERAL, HR, IT, FACILITIES, CULTURE

### `Announcement` table: `announcements`

| Column | Notes |
|---|---|
| `is_pinned` | Boolean — pinned announcements shown at top |
| `created_by_id` | FK→employees (MANAGER or above can create) |

---

## `ai_audit_log.py`

### Enums

| Enum | Values |
|---|---|
| `AIIntent` | POLICY_QA, SQL_QUERY, HR_ACTION, ROUTER, UNKNOWN |
| `ActionStatus` | SUCCESS, REFUSED, ERROR |

### `AIAuditLog` table: `ai_audit_logs`

Append-only audit trail. Never updated after insert.

| Column | Notes |
|---|---|
| `user_id` | FK→employees |
| `role` | Denormalized string (snapshot of role at query time) |
| `message` | Full user message text |
| `intent` | Classified intent |
| `tool_name` | Agent that handled the request (e.g., `"policy_rag"`) |
| `action_status` | SUCCESS / REFUSED / ERROR |
| `records_accessed` | JSON string — list of policy titles, SQL queries, or action results |
| `created_at` | Timestamp |

---

## `role_category_access.py`

Join table for role-based policy access.

### `RoleCategoryAccess` table: `role_category_access`

| Column | Type |
|---|---|
| `id` | Integer PK |
| `role` | String (EmployeeRole value) |
| `category` | String (PolicyCategory value) |

One row per (role, category) pair. Managed entirely via `/admin/roles` and `/admin/categories` endpoints. Read by `policy_rag._get_accessible_categories()`.

---

## `policy_group.py`

Named groups that override role-based policy access for specific employees.

### `PolicyGroup` table: `policy_groups`

| Column | Notes |
|---|---|
| `name` | String unique — normalized key (lowercase, underscores) |

### `GroupCategoryAccess` table: `group_category_access`

| Column | Notes |
|---|---|
| `group_name` | String FK→policy_groups.name |
| `category` | String (PolicyCategory value) |

An employee with `policy_group = "engineering_contractors"` gets the categories from `group_category_access` for that group name, bypassing their `EmployeeRole` lookup.

---

## Other models (brief)

### `department.py` — `Department`

| Column | Notes |
|---|---|
| `name` | String |
| `description` | Text |
| `head_id` | FK→employees nullable — department head |

### `project.py` — `Project`, `EmployeeProject`

`Project`: name, description, status (PLANNING/ONGOING/COMPLETED/ON_HOLD), start_date, end_date.

`EmployeeProject`: join table with `employee_id`, `project_id`, `role` (string, e.g., "Lead"), `assigned_at`, `is_active`.

### `skill.py` — `Skill`, `EmployeeSkill`

`Skill`: name, category.

`EmployeeSkill`: employee_id, skill_id, proficiency (string).

### `job_history.py` — `JobHistory`

Tracks role/department changes: employee_id, job_title, department_id, start_date, end_date, reason_for_change.

### `onboarding.py` — `OnboardingTask`

Tracks new-hire onboarding steps per employee: title, description, is_completed, due_date.

### `payroll.py` — `PayrollRecord`

Monthly payroll snapshot: employee_id, pay_period_start/end, gross/net/deductions, payment_date, status.
