"""
NL→SQL agent with schema-aware generation, role-based access filtering,
and guardrail validation before execution.
"""
import logging
import re
from dataclasses import dataclass
from typing import TypedDict, List, Any, Optional, Union

_log = logging.getLogger(__name__)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import AI_MAX_TOKENS_SQL_AGENT_QUERY, AI_MAX_TOKENS_SQL_AGENT_SUMMARY
from app.services.ai.core.memory.context import build_history_block
from app.models.employee import Employee, EmployeeRole
from app.services.ai import factory as _factory
from app.services.ai.core.security.sql_safety import validate_sql, scrub_forbidden_columns, mask_for_llm, SQLGuardError
from app.services.ai.core.memory.memory import build_memory_section, maybe_summarize, store_agent_turn

# Tables the SQL agent may query — sorted by safety
_ALLOWED_TABLES = [
    "employees", "departments", "projects", "employee_projects",
    "skills", "employee_skills", "job_history", "leave_requests",
    "leave_balances", "tickets",
]

# Schema description with sensitive columns pre-excluded
_TABLE_SCHEMAS = {
    "employees": (
        "employees(id, employee_code, name, email, "
        "role [values: EMPLOYEE|MANAGER|ADMIN|HR|MARKETING|C_LEVEL — system access level ONLY, NOT job function], "
        "department_id, manager_id, "
        "job_title [free-text profession e.g. 'Software Engineer', 'Data Analyst', 'Product Manager' — "
        "use LOWER(job_title) LIKE '%keyword%' to find employees by profession], "
        "employment_type [values: FULL_TIME|PART_TIME|CONTRACT], "
        "status [values: ACTIVE|INACTIVE|NOTICE|TERMINATED], joining_date, "
        "current_salary_usd [ROLE-GATED — only accessible per access rules; unauthorized access → ACCESS_DENIED])"
    ),
    "departments": "departments(id, name, description, head_id)",
    "projects": "projects(id, name, description, status [values: PLANNING|ONGOING|COMPLETED|ON_HOLD], start_date, end_date)",
    "employee_projects": "employee_projects(id, employee_id, project_id, role, assigned_at, is_active)",
    "skills": "skills(id, name, category)",
    "employee_skills": "employee_skills(id, employee_id, skill_id, proficiency)",
    "job_history": "job_history(id, employee_id, job_title, department_id, start_date, end_date, reason_for_change)",
    "leave_requests": (
        "leave_requests(id, employee_id, leave_type [values: CASUAL|SICK|ANNUAL|UNPAID], "
        "start_date, end_date, is_half_day, half_day_period [values: MORNING|AFTERNOON], "
        "reason, status [values: PENDING|APPROVED|REJECTED|CANCELLED], approved_by_id, approved_at, created_at)"
    ),
    "leave_balances": (
        "leave_balances(id, employee_id, year, casual_leave_total, casual_leave_used, "
        "sick_leave_total, sick_leave_used, annual_leave_total, annual_leave_used)"
    ),
    "tickets": (
        "tickets(id, title, description, category, priority, status, "
        "created_by_id, assigned_to_id, resolved_at, created_at)"
    ),
}

_SYSTEM_TEMPLATE = """You are a read-only SQL generation agent for an HR SQLite database.

Your job is to translate natural language questions into safe, correct SQL SELECT statements.
You MUST NOT execute anything or invent data — output SQL only.

----------------------
CORE BEHAVIOR
----------------------

1. Understand Intent
   - Interpret the question and identify which tables and columns answer it.
   - Use conversation history to resolve follow-up references ("their manager", "the same project").

2. Schema Adherence
   - Use ONLY the tables and columns listed in the schema section below.
   - Never reference, guess, or hallucinate columns not in the schema.

3. Access Enforcement
   - Apply ALL filters from the access rules without exception.
   - Access rules are non-negotiable. Never generate a query that bypasses them.

4. Output Discipline
   - Return a single SELECT statement. No mutations (INSERT/UPDATE/DELETE), no DDL.
   - No markdown fences, no explanation, no trailing semicolon.

5. Sentinels
   - Access rules prohibit this query → respond exactly: ACCESS_DENIED
   - Question cannot be answered from available schema → respond exactly: CANNOT_ANSWER

----------------------
SCHEMA
----------------------

{schema}

----------------------
ACCESS RULES
----------------------

{access_rules}

----------------------
SENSITIVE DATA POLICY
----------------------

NEVER SELECT these columns for any role:
  bank_account_number, bank_account_name, bank_branch, bank_ifsc,
  pan_number, pan_name, pan_dob, hashed_password,
  profile_photo_path, profile_photo_mime

If the user asks about bank/IFSC/PAN/Aadhaar details, respond exactly (no SQL):
  "For security, bank and PAN details are only viewable on your Profile page."

date_of_birth is NOT in the forbidden list.
Include it in SELECT when the access rules above permit it.

current_salary_usd is ROLE-GATED (not absolutely forbidden):
  - ADMIN / HR / C_LEVEL: may SELECT current_salary_usd for any employee.
  - MANAGER: may SELECT current_salary_usd only for own record OR direct reports (manager_id = their id).
  - EMPLOYEE / MARKETING: may SELECT current_salary_usd only for their OWN record (id = their id).
  - Any query that would expose another employee's salary to an unauthorized role → respond exactly: ACCESS_DENIED

----------------------
DECISION RULE
----------------------

- Clear, permitted query → output SQL only, no explanation
- User asks about bank/PAN → output the profile-page message above, nothing else
- User asks about salary for another employee they are not authorized to see → ACCESS_DENIED
- Ambiguous column or join → pick the most reasonable schema interpretation
- Access violation → ACCESS_DENIED
- Unanswerable from available schema → CANNOT_ANSWER

{memory_section}"""


class SQLResult(TypedDict):
    answer: str
    sql: str
    rows: List[Any]
    row_count: int


def _build_access_rules(user: Employee, db: Session) -> str:
    if user.role in (EmployeeRole.ADMIN, EmployeeRole.HR, EmployeeRole.C_LEVEL):
        label = user.role.value.title()
        return (
            f"The current user's role is {label} (employee_id={user.id}). "
            f"This role has full read access to all allowed tables and all employees' data, "
            f"including current_salary_usd and date_of_birth for all employees. "
            f"No row filters are needed — generate SQL that returns all requested rows."
        )

    if user.role == EmployeeRole.MANAGER:
        return (
            f"Manager role (employee_id={user.id}). "
            f"For the employees table: "
            f"  - Public fields (id, name, role, job_title, department_id, employment_type, status, manager_id, joining_date): "
            f"    no row filter needed — you may query any employee for org-chart lookups. "
            f"  - current_salary_usd and date_of_birth: only for your own record (id = {user.id}) "
            f"    or your direct reports (manager_id = {user.id}). "
            f"For other employee-specific tables (leave_requests, leave_balances, tickets, "
            f"employee_projects, employee_skills, job_history): "
            f"filter by employee_id IN (SELECT id FROM employees WHERE id = {user.id} OR manager_id = {user.id}) "
            f"or created_by_id in same set. "
            f"For project/department catalog queries, no filter needed."
        )

    # EMPLOYEE and MARKETING — own data only, plus read-only public fields of direct manager
    return (
        f"{user.role.value.title()} role (employee_id={user.id}). "
        f"For the employees table: "
        f"  - Own record: filter by id = {user.id} (the primary key column is 'id', NOT 'employee_id'). "
        f"  - Direct manager lookup ONLY: you may read public fields "
        f"    (id, name, email, job_title, role, department_id, employment_type, status, manager_id, joining_date) "
        f"    of the employee whose id matches your manager_id. "
        f"    Allowed pattern: JOIN employees AS mgr ON e.manager_id = mgr.id WHERE e.id = {user.id}. "
        f"  - Any other employee row is ACCESS_DENIED. "
        f"For other employee-specific tables (leave_requests, leave_balances, tickets, "
        f"employee_projects, employee_skills, job_history): "
        f"always filter by employee_id = {user.id} or created_by_id = {user.id}. "
        f"current_salary_usd and date_of_birth may only be queried where employees.id = {user.id} (own record only). "
        f"For catalog queries (projects, departments, skills — read-only lists), no filter needed."
    )



_SENTINEL_ACCESS_DENIED = "ACCESS_DENIED"
_SENTINEL_CANNOT_ANSWER = "CANNOT_ANSWER"


@dataclass(frozen=True)
class _DirectAnswer:
    """LLM answered from injected context (own salary/DOB or bank/PAN redirect)."""
    text: str


@dataclass(frozen=True)
class _AccessDenied:
    """Query blocked by access rules."""


# Return type for _extract_sql: SQL string | _DirectAnswer | _AccessDenied | None
_SqlExtractResult = Union[str, _DirectAnswer, _AccessDenied, None]


def _extract_sql(raw: str) -> _SqlExtractResult:
    raw = raw.strip()
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).strip("` \n")
    upper = raw.upper().strip()

    if upper == _SENTINEL_ACCESS_DENIED or upper.startswith(_SENTINEL_ACCESS_DENIED):
        return _AccessDenied()

    if upper == _SENTINEL_CANNOT_ANSWER or upper.startswith(_SENTINEL_CANNOT_ANSWER):
        return None

    select_match = re.search(r"\bSELECT\b.*", raw, re.IGNORECASE | re.DOTALL)
    if select_match:
        return select_match.group(0).split(";")[0].strip()

    if _SENTINEL_ACCESS_DENIED in upper:
        return _AccessDenied()

    # No SELECT found — LLM produced prose (own-data context reply or bank/PAN redirect)
    if raw and _SENTINEL_CANNOT_ANSWER not in upper:
        return _DirectAnswer(text=raw)

    return None


def _rows_to_dicts(result) -> List[dict]:
    keys = list(result.keys())
    return [dict(zip(keys, row)) for row in result.fetchall()]


def run_sql_query(db: Session, user: Employee, question: str, history: list = None, session_id: Optional[str] = None) -> SQLResult:
    maybe_summarize(db, user.id, session_id, "sql_agent", history or [])
    mem = build_memory_section(db, user.id, session_id, "sql_agent")
    schema_block = "\n".join(_TABLE_SCHEMAS[t] for t in _ALLOWED_TABLES)
    access_rules = _build_access_rules(user, db)
    system = _SYSTEM_TEMPLATE.format(
        schema=schema_block,
        access_rules=access_rules,
        memory_section=mem,
    )

    history_block = build_history_block(history or [])
    prompt = f"{history_block} {question}" if history_block else question

    llm = _factory.get_llm_provider()
    raw_sql = llm.generate(prompt, system=system, max_tokens=AI_MAX_TOKENS_SQL_AGENT_QUERY)
    sql = _extract_sql(raw_sql)

    if isinstance(sql, _AccessDenied):
        return SQLResult(
            answer="Access denied: you don't have permission to view this information.",
            sql="",
            rows=[],
            row_count=0,
        )

    if isinstance(sql, _DirectAnswer):
        return SQLResult(answer=sql.text, sql="", rows=[], row_count=0)

    if sql is None:
        return SQLResult(
            answer="No data found to answer your question.",
            sql="",
            rows=[],
            row_count=0,
        )

    try:
        validated_sql = validate_sql(sql, role=user.role)
    except SQLGuardError as e:
        return SQLResult(
            answer=f"That query is not permitted: {e}",
            sql="",
            rows=[],
            row_count=0,
        )

    try:
        result = db.execute(text(validated_sql))
        rows = _rows_to_dicts(result)
        rows = scrub_forbidden_columns(rows, role=user.role)
    except Exception:
        _log.exception("SQL execution failed user_id=%s sql=%r", user.id, validated_sql)
        return SQLResult(
            answer="The query could not be executed. Please rephrase your question.",
            sql="",
            rows=[],
            row_count=0,
        )

    # Generate a natural-language summary
    if not rows:
        answer = "No results found for your query."
    else:
        # Mask sensitive column values before passing to LLM — actual values stay in `rows`
        masked_sample = mask_for_llm(rows[:3])
        summary_prompt = (
            f"The user asked: {question}\n"
            f"SQL executed: {validated_sql}\n"
            f"Row count: {len(rows)}\n"
            f"First few rows (sample): {masked_sample}\n\n"
            "Write a concise 1-2 sentence natural language summary of these results. "
            "Do not mention SQL or technical details. "
            "If a column value shows [REDACTED], the actual value IS visible to the user in the data table — "
            "do NOT say the value was redacted or hidden. Instead, simply state what data was found "
            "(e.g. 'Your salary record is available in the results.' or 'Your current salary is shown below.')."
        )
        answer = llm.generate(summary_prompt, system="Summarize HR data query results clearly.", max_tokens=AI_MAX_TOKENS_SQL_AGENT_SUMMARY)

    if session_id:
        store_agent_turn(db, user.id, session_id, "sql_agent", f"Queried: {question[:120]}")

    return SQLResult(answer=answer, sql=validated_sql, rows=rows, row_count=len(rows))
