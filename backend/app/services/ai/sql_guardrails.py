"""
SQL safety layer: blocks DDL/DML, forbidden columns, multi-statement queries,
and enforces row limits before any query reaches the DB.
"""
import re
from typing import Optional

_FORBIDDEN_COLUMNS = frozenset({
    "hashed_password",
    "bank_account_number",
    "bank_account_name",
    "bank_branch",
    "bank_ifsc",
    "pan_number",
    "pan_name",
    "pan_dob",
    "date_of_birth",
    "current_salary_usd",
    "profile_photo_path",
    "profile_photo_mime",
})

_BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|PRAGMA|ATTACH|DETACH)\b",
    re.IGNORECASE,
)

_MAX_ROWS = 100


class SQLGuardError(ValueError):
    pass


def validate_sql(sql: str) -> str:
    """
    Validate and normalize SQL. Returns cleaned SQL or raises SQLGuardError.
    Never passes raw DB errors to callers — always raise SQLGuardError with safe messages.
    """
    sql = sql.strip().rstrip(";")

    # Block multi-statement (semicolons mid-query)
    if ";" in sql:
        raise SQLGuardError("Only a single SQL statement is allowed per request.")

    # Block DDL / DML keywords
    match = _BLOCKED_KEYWORDS.search(sql)
    if match:
        raise SQLGuardError(f"SQL keyword '{match.group().upper()}' is not permitted.")

    # Must start with SELECT
    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        raise SQLGuardError("Only SELECT queries are permitted.")

    # Check forbidden columns
    _check_forbidden_columns(sql)

    # Reject unbalanced parentheses (catches truncated model output)
    if sql.count("(") != sql.count(")"):
        raise SQLGuardError("Generated SQL has unbalanced parentheses. Please rephrase your question.")

    # Inject LIMIT if missing
    sql = _enforce_row_limit(sql)

    return sql


def _check_forbidden_columns(sql: str) -> None:
    lower = sql.lower()
    for col in _FORBIDDEN_COLUMNS:
        # Match as a word boundary to avoid partial matches
        if re.search(r"\b" + re.escape(col) + r"\b", lower):
            raise SQLGuardError(f"Access to column '{col}' is not permitted.")


def scrub_forbidden_columns(rows: list[dict]) -> list[dict]:
    """Remove any forbidden columns from result rows (defence-in-depth)."""
    return [
        {k: v for k, v in row.items() if k not in _FORBIDDEN_COLUMNS}
        for row in rows
    ]


def _enforce_row_limit(sql: str) -> str:
    if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        sql = f"{sql} LIMIT {_MAX_ROWS}"
    else:
        # Replace any LIMIT that exceeds _MAX_ROWS
        def cap_limit(m: re.Match) -> str:
            n = int(m.group(1))
            return f"LIMIT {min(n, _MAX_ROWS)}"
        sql = re.sub(r"\bLIMIT\s+(\d+)\b", cap_limit, sql, flags=re.IGNORECASE)
    return sql


def safe_column_list(columns: Optional[list[str]] = None) -> str:
    """Return a safe comma-separated column list with forbidden columns excluded."""
    if not columns:
        return "*"
    safe = [c for c in columns if c not in _FORBIDDEN_COLUMNS]
    return ", ".join(safe) if safe else "*"
