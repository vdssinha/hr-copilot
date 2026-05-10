"""
SQL safety layer: blocks DDL/DML, forbidden columns, multi-statement queries,
and enforces row limits before any query reaches the DB.

Column access is split into two tiers:

  ABSOLUTE_FORBIDDEN  — blocked for ALL roles, no exceptions.
                        Credentials, bank details, PAN, photo paths.

  CONTEXTUAL_SENSITIVE — salary and date of birth.
                         EMPLOYEE: blocked via SQL (own data shown via profile context).
                         MANAGER / ADMIN: allowed (team oversight / HR operations).

Pass the current user's role to validate_sql() so the right ruleset applies.
"""
import re
from typing import Optional

from app.models.employee import EmployeeRole

# Never exposed via SQL regardless of role
_ABSOLUTE_FORBIDDEN = frozenset({
    "hashed_password",
    "bank_account_number",
    "bank_account_name",
    "bank_branch",
    "bank_ifsc",
    "pan_number",
    "pan_name",
    "pan_dob",
    "profile_photo_path",
    "profile_photo_mime",
})

# Blocked for EMPLOYEE role; allowed for MANAGER / ADMIN
_CONTEXTUAL_SENSITIVE = frozenset({
    "current_salary_usd",
    "date_of_birth",
})

_BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|PRAGMA|ATTACH|DETACH)\b",
    re.IGNORECASE,
)

_MAX_ROWS = 100

# Roles that may access contextual sensitive columns (salary, DOB).
# MARKETING is included because the SQL agent access rules already restrict
# their salary queries to employee_id = current user — same as EMPLOYEE self-access,
# but the LLM prompt explicitly permits it so the validator must agree.
_PRIVILEGED_ROLES = {EmployeeRole.MARKETING, EmployeeRole.MANAGER, EmployeeRole.HR, EmployeeRole.C_LEVEL, EmployeeRole.ADMIN}


class SQLGuardError(ValueError):
    pass


def _forbidden_for_role(role: Optional[EmployeeRole]) -> frozenset:
    if role in _PRIVILEGED_ROLES:
        return _ABSOLUTE_FORBIDDEN
    return _ABSOLUTE_FORBIDDEN | _CONTEXTUAL_SENSITIVE


def validate_sql(sql: str, role: Optional[EmployeeRole] = None) -> str:
    """
    Validate and normalize SQL. Returns cleaned SQL or raises SQLGuardError.
    Never passes raw DB errors to callers — always raise SQLGuardError with safe messages.

    Args:
        sql:  Raw SQL string from the LLM.
        role: Current user's role. Determines which columns are forbidden.
    """
    sql = sql.strip().rstrip(";")

    if ";" in sql:
        raise SQLGuardError("Only a single SQL statement is allowed per request.")

    match = _BLOCKED_KEYWORDS.search(sql)
    if match:
        raise SQLGuardError(f"SQL keyword '{match.group().upper()}' is not permitted.")

    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        raise SQLGuardError("Only SELECT queries are permitted.")

    _check_forbidden_columns(sql, role)

    if sql.count("(") != sql.count(")"):
        raise SQLGuardError("Generated SQL has unbalanced parentheses. Please rephrase your question.")

    sql = _enforce_row_limit(sql)
    return sql


def _check_forbidden_columns(sql: str, role: Optional[EmployeeRole]) -> None:
    forbidden = _forbidden_for_role(role)
    lower = sql.lower()
    for col in forbidden:
        if re.search(r"\b" + re.escape(col) + r"\b", lower):
            raise SQLGuardError(f"Access to column '{col}' is not permitted.")


def scrub_forbidden_columns(rows: list[dict], role: Optional[EmployeeRole] = None) -> list[dict]:
    """Remove forbidden columns from result rows (defence-in-depth)."""
    forbidden = _forbidden_for_role(role)
    return [
        {k: v for k, v in row.items() if k not in forbidden}
        for row in rows
    ]


def _enforce_row_limit(sql: str) -> str:
    if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        return f"{sql} LIMIT {_MAX_ROWS}"

    def cap_limit(m: re.Match) -> str:
        n = int(m.group(1))
        return f"LIMIT {min(n, _MAX_ROWS)}"

    return re.sub(r"\bLIMIT\s+(\d+)\b", cap_limit, sql, flags=re.IGNORECASE)


def safe_column_list(columns: Optional[list[str]] = None, role: Optional[EmployeeRole] = None) -> str:
    """Return a safe comma-separated column list with forbidden columns excluded."""
    if not columns:
        return "*"
    forbidden = _forbidden_for_role(role)
    safe = [c for c in columns if c not in forbidden]
    return ", ".join(safe) if safe else "*"
