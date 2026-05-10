"""
NL→SQL agent with schema-aware generation, role-based access filtering,
and guardrail validation before execution.
"""
import re
from typing import TypedDict, List, Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import AI_MAX_TOKENS_SQL_AGENT_QUERY, AI_MAX_TOKENS_SQL_AGENT_SUMMARY
from app.services.ai.context import build_history_block
from app.models.employee import Employee, EmployeeRole
from app.services.ai import factory as _factory
from app.services.ai.sql_guardrails import validate_sql, scrub_forbidden_columns, SQLGuardError
from app.services.ai.memory import build_memory_section, maybe_summarize, store_agent_turn

# Tables the SQL agent may query — sorted by safety
_ALLOWED_TABLES = [
    "employees", "departments", "projects", "employee_projects",
    "skills", "employee_skills", "job_history", "leave_requests",
    "leave_balances", "tickets",
]

# Schema description with sensitive columns pre-excluded
_TABLE_SCHEMAS = {
    "employees": (
        "employees(id, employee_code, name, email, role [values: EMPLOYEE|MANAGER|ADMIN|HR|MARKETING|C_LEVEL], "
        "department_id, manager_id, job_title, employment_type [values: FULL_TIME|PART_TIME|CONTRACT], "
        "status [values: ACTIVE|INACTIVE|NOTICE|TERMINATED], joining_date, current_salary_usd)"
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
DECISION RULE
----------------------

- Clear, permitted query → generate SQL
- Ambiguous column or join → pick the most reasonable interpretation from schema
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
            f"{label} role: full read access to all allowed tables and all employees' data, "
            f"including current_salary_usd for all employees."
        )

    if user.role == EmployeeRole.MANAGER:
        return (
            f"Manager role (employee_id={user.id}). "
            f"For the employees table: "
            f"  - Public fields (id, name, role, job_title, department_id, employment_type, status, manager_id, joining_date): "
            f"    no row filter needed — you may query any employee for org-chart lookups. "
            f"  - current_salary_usd: only allowed for your own record (id = {user.id}) "
            f"    or your direct reports (manager_id = {user.id}). "
            f"For other employee-specific tables (leave_requests, leave_balances, tickets, "
            f"employee_projects, employee_skills, job_history): "
            f"filter by employee_id IN (SELECT id FROM employees WHERE id = {user.id} OR manager_id = {user.id}) "
            f"or created_by_id in same set. "
            f"For project/department catalog queries, no filter needed."
        )

    if user.role == EmployeeRole.MARKETING:
        return (
            f"Marketing role (employee_id={user.id}). "
            f"For employee-specific data (leave_requests, leave_balances, tickets, employee_projects, employee_skills, employees), "
            f"always filter by employee_id = {user.id} or created_by_id = {user.id}. "
            f"current_salary_usd may be queried only for employee_id = {user.id} (own record). "
            f"For catalog queries (projects, departments, skills — read-only lists), no filter needed."
        )

    # EMPLOYEE — own data only, no salary access
    return (
        f"Employee role (employee_id={user.id}). "
        f"For employee-specific data (leave_requests, leave_balances, tickets, employee_projects, employee_skills, employees), "
        f"always filter by employee_id = {user.id} or created_by_id = {user.id}. "
        f"current_salary_usd may be queried only for employee_id = {user.id} (own record). "
        f"For catalog queries (projects, departments, skills — read-only lists), no filter needed."
    )


_SENTINEL_ACCESS_DENIED = "ACCESS_DENIED"
_SENTINEL_CANNOT_ANSWER = "CANNOT_ANSWER"


def _extract_sql(raw: str) -> Optional[str]:
    raw = raw.strip()
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).strip("` \n")
    upper = raw.upper().strip()
    if upper == _SENTINEL_ACCESS_DENIED or upper.startswith(_SENTINEL_ACCESS_DENIED):
        return _SENTINEL_ACCESS_DENIED
    if upper == _SENTINEL_CANNOT_ANSWER or _SENTINEL_CANNOT_ANSWER in upper:
        return None
    select_match = re.search(r"\bSELECT\b.*", raw, re.IGNORECASE | re.DOTALL)
    if select_match:
        raw = select_match.group(0)
    elif _SENTINEL_ACCESS_DENIED in upper:
        return _SENTINEL_ACCESS_DENIED
    else:
        return None  # no valid SQL found — treat as CANNOT_ANSWER
    return raw.split(";")[0].strip()


def _rows_to_dicts(result) -> List[dict]:
    keys = list(result.keys())
    return [dict(zip(keys, row)) for row in result.fetchall()]


def run_sql_query(db: Session, user: Employee, question: str, history: list = None, session_id: Optional[str] = None) -> SQLResult:
    maybe_summarize(db, user.id, session_id, "sql_agent", history or [])
    mem = build_memory_section(db, user.id, session_id, "sql_agent")
    schema_block = "\n".join(_TABLE_SCHEMAS[t] for t in _ALLOWED_TABLES)
    access_rules = _build_access_rules(user, db)
    system = _SYSTEM_TEMPLATE.format(schema=schema_block, access_rules=access_rules, memory_section=mem)

    history_block = build_history_block(history or [])
    prompt = f"{history_block} {question}" if history_block else question

    llm = _factory.get_llm_provider()
    raw_sql = llm.generate(prompt, system=system, max_tokens=AI_MAX_TOKENS_SQL_AGENT_QUERY)
    sql = _extract_sql(raw_sql)

    if sql == _SENTINEL_ACCESS_DENIED:
        return SQLResult(
            answer="Access denied: you don't have permission to view this information.",
            sql="",
            rows=[],
            row_count=0,
        )

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
        # Never leak raw DB errors
        return SQLResult(
            answer="The query could not be executed. Please rephrase your question.",
            sql=validated_sql,
            rows=[],
            row_count=0,
        )

    # Generate a natural-language summary
    if not rows:
        answer = "No results found for your query."
    else:
        summary_prompt = (
            f"The user asked: {question}\n"
            f"SQL executed: {validated_sql}\n"
            f"Row count: {len(rows)}\n"
            f"First few rows (sample): {rows[:3]}\n\n"
            "Write a concise 1-2 sentence natural language summary of these results. "
            "Do not mention SQL or technical details."
        )
        answer = llm.generate(summary_prompt, system="Summarize HR data query results clearly.", max_tokens=AI_MAX_TOKENS_SQL_AGENT_SUMMARY)

    if session_id:
        store_agent_turn(db, user.id, session_id, "sql_agent", f"Queried: {question[:120]}")

    return SQLResult(answer=answer, sql=validated_sql, rows=rows, row_count=len(rows))
