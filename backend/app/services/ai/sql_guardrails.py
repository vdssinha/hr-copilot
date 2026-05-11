"""
SQL safety layer: blocks DDL/DML, forbidden columns, multi-statement queries,
and enforces row limits before any query reaches the DB.

Column access is split into two tiers:

  ABSOLUTE_FORBIDDEN  — blocked for ALL roles at SQL validation time.
                        Credentials, bank details, PAN, photo paths.
                        Also scrubbed from rows returned to the frontend.

  LLM_MASKED          — salary and date of birth.
                        Returned in raw rows to the frontend so the UI
                        can display them, but replaced with [REDACTED]
                        in any sample rows passed to the LLM for summary.
                        Row-level scope (own vs team vs all) is enforced
                        by per-role LLM access rules, not by the validator.
"""
import re
from typing import Optional

from app.models.employee import EmployeeRole

# Never exposed via SQL, never returned to frontend, never in LLM context
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

# Returned to frontend in raw rows; replaced with [REDACTED] in LLM summary calls.
# Row-level access (own / direct-reports / all) is enforced by per-role LLM access rules.
_LLM_MASKED_COLUMNS = frozenset({
    "current_salary_usd",
    "date_of_birth",
})

_BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|PRAGMA|ATTACH|DETACH)\b",
    re.IGNORECASE,
)

_MAX_ROWS = 100


class SQLGuardError(ValueError):
    pass


def validate_sql(sql: str, role: Optional[EmployeeRole] = None) -> str:
    """
    Validate and normalize SQL. Returns cleaned SQL or raises SQLGuardError.
    Never passes raw DB errors to callers — always raise SQLGuardError with safe messages.

    Args:
        sql:  Raw SQL string from the LLM.
        role: Current user's role (reserved for future role-specific rules).
    """
    sql = sql.strip().rstrip(";")

    if ";" in sql:
        raise SQLGuardError("Only a single SQL statement is allowed per request.")

    match = _BLOCKED_KEYWORDS.search(sql)
    if match:
        raise SQLGuardError(f"SQL keyword '{match.group().upper()}' is not permitted.")

    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        raise SQLGuardError("Only SELECT queries are permitted.")

    _check_forbidden_columns(sql)

    if sql.count("(") != sql.count(")"):
        raise SQLGuardError("Generated SQL has unbalanced parentheses. Please rephrase your question.")

    sql = _enforce_row_limit(sql)
    return sql


def _check_forbidden_columns(sql: str) -> None:
    lower = sql.lower()
    for col in _ABSOLUTE_FORBIDDEN:
        if re.search(r"\b" + re.escape(col) + r"\b", lower):
            raise SQLGuardError(f"Access to column '{col}' is not permitted.")


def scrub_forbidden_columns(rows: list[dict], role: Optional[EmployeeRole] = None) -> list[dict]:
    """Remove absolute-forbidden columns from result rows (defence-in-depth for frontend)."""
    return [
        {k: v for k, v in row.items() if k not in _ABSOLUTE_FORBIDDEN}
        for row in rows
    ]


def mask_for_llm(rows: list[dict]) -> list[dict]:
    """
    Replace sensitive column values with [REDACTED] before passing sample rows
    to the LLM for natural-language summary generation.

    The unmasked rows are still returned to the frontend — this mask only
    prevents actual salary/DOB figures from being transmitted to the LLM provider.
    """
    return [
        {k: "[REDACTED]" if k in _LLM_MASKED_COLUMNS else v for k, v in row.items()}
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
    """Return a safe comma-separated column list with absolute-forbidden columns excluded."""
    if not columns:
        return "*"
    safe = [c for c in columns if c not in _ABSOLUTE_FORBIDDEN]
    return ", ".join(safe) if safe else "*"
