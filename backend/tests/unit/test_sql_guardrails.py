"""
Unit tests for sql_guardrails — the SQL safety layer.
No DB or LLM needed.
"""
import pytest
from app.services.ai.sql_guardrails import (
    validate_sql, scrub_forbidden_columns, SQLGuardError,
)


# ─── validate_sql: DDL / DML blocking ────────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "INSERT INTO employees (name) VALUES ('hacker')",
    "UPDATE employees SET role = 'ADMIN'",
    "DELETE FROM leave_requests",
    "DROP TABLE employees",
    "ALTER TABLE employees ADD COLUMN pwned TEXT",
    "CREATE TABLE shadow AS SELECT * FROM employees",
    "REPLACE INTO employees (id, name) VALUES (1, 'x')",
    "TRUNCATE TABLE employees",
    "PRAGMA table_info(employees)",
    "ATTACH DATABASE '/etc/passwd' AS p",
    "DETACH DATABASE p",
])
def test_blocks_ddl_dml(sql):
    with pytest.raises(SQLGuardError, match="not permitted"):
        validate_sql(sql)


# ─── validate_sql: must be SELECT ────────────────────────────────────────────

def test_blocks_non_select():
    with pytest.raises(SQLGuardError, match="Only SELECT"):
        validate_sql("EXPLAIN SELECT * FROM employees")


def test_passes_select():
    result = validate_sql("SELECT id, name FROM employees")
    assert result.upper().startswith("SELECT")


def test_passes_select_with_joins():
    sql = (
        "SELECT e.name, d.name FROM employees e "
        "JOIN departments d ON e.department_id = d.id "
        "WHERE e.status = 'ACTIVE'"
    )
    result = validate_sql(sql)
    assert "SELECT" in result.upper()


# ─── validate_sql: forbidden columns ─────────────────────────────────────────

@pytest.mark.parametrize("col", [
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
])
def test_blocks_all_forbidden_columns(col):
    with pytest.raises(SQLGuardError, match=col):
        validate_sql(f"SELECT {col} FROM employees")


def test_forbidden_column_case_insensitive():
    with pytest.raises(SQLGuardError):
        validate_sql("SELECT HASHED_PASSWORD FROM employees")


def test_forbidden_column_in_where_clause():
    with pytest.raises(SQLGuardError):
        validate_sql("SELECT id FROM employees WHERE hashed_password = 'x'")


# ─── validate_sql: multi-statement blocking ───────────────────────────────────

def test_blocks_multi_statement():
    with pytest.raises(SQLGuardError, match="single SQL statement"):
        validate_sql("SELECT 1; DROP TABLE employees")


# ─── validate_sql: unbalanced parentheses ────────────────────────────────────

def test_blocks_unbalanced_parens():
    with pytest.raises(SQLGuardError, match="unbalanced"):
        validate_sql("SELECT id FROM employees WHERE id IN (1, 2, 3")


def test_passes_balanced_parens():
    result = validate_sql("SELECT id FROM employees WHERE id IN (1, 2, 3)")
    assert result is not None


# ─── validate_sql: LIMIT injection ───────────────────────────────────────────

def test_injects_limit_when_missing():
    result = validate_sql("SELECT id FROM employees")
    assert "LIMIT 100" in result


def test_caps_limit_over_100():
    result = validate_sql("SELECT id FROM employees LIMIT 500")
    assert "LIMIT 100" in result
    assert "LIMIT 500" not in result


def test_preserves_limit_under_100():
    result = validate_sql("SELECT id FROM employees LIMIT 10")
    assert "LIMIT 10" in result


def test_strips_trailing_semicolon():
    result = validate_sql("SELECT id FROM employees;")
    assert ";" not in result


# ─── scrub_forbidden_columns ─────────────────────────────────────────────────

def test_scrub_removes_forbidden_keys():
    rows = [
        {"id": 1, "name": "Alice", "hashed_password": "secret", "bank_account_number": "12345"},
        {"id": 2, "name": "Bob", "current_salary_usd": 100000.0},
    ]
    scrubbed = scrub_forbidden_columns(rows)
    for row in scrubbed:
        assert "hashed_password" not in row
        assert "bank_account_number" not in row
        assert "current_salary_usd" not in row
        assert "id" in row
        assert "name" in row


def test_scrub_passthrough_clean_rows():
    rows = [{"id": 1, "name": "Alice", "role": "EMPLOYEE"}]
    scrubbed = scrub_forbidden_columns(rows)
    assert scrubbed == rows


def test_scrub_empty_list():
    assert scrub_forbidden_columns([]) == []
