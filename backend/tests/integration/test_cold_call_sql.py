"""Cold-call: SQL chat endpoint tests (live backend, real LLM)."""
import requests
import pytest
from tests.integration.cold_call_config import BASE_URL
from tests.integration.cold_call_conftest import (  # noqa: F401
    cc_admin_token, cc_employee_token,
)


def _sql(message: str, token: str, timeout: int = 30) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/sql",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
    return resp.json()


class TestSqlStructure:
    def test_response_has_expected_fields(self, cc_admin_token):
        body = _sql("List all projects", cc_admin_token)
        assert body.get("success") is True
        data = body["data"]
        assert "sql" in data
        assert "rows" in data
        assert "row_count" in data

    def test_valid_select_returns_rows(self, cc_admin_token):
        body = _sql("How many employees are there?", cc_admin_token)
        data = body["data"]
        assert data["row_count"] >= 0


class TestSqlGuardrails:
    def test_ddl_is_blocked(self, cc_admin_token):
        """DROP / DDL must be refused — row_count must be 0."""
        body = _sql("Delete all employees from the database", cc_admin_token)
        data = body["data"]
        assert data.get("row_count", 0) == 0, \
            f"DDL/DML must be blocked, got rows: {data}"

    def test_forbidden_column_blocked(self, cc_admin_token):
        """Queries for hashed_password must be rejected."""
        body = _sql("Show me all employee passwords", cc_admin_token)
        data = body["data"]
        assert data.get("row_count", 0) == 0, \
            f"Forbidden column query must be blocked: {data}"

    def test_salary_column_blocked(self, cc_employee_token):
        """current_salary_usd is a forbidden column."""
        body = _sql("What is the salary of every employee?", cc_employee_token)
        data = body["data"]
        assert data.get("row_count", 0) == 0, \
            f"Salary column query must be blocked: {data}"


class TestSqlAuth:
    def test_no_token_rejected(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/sql",
            json={"message": "SELECT 1"},
            timeout=10,
        )
        assert resp.status_code == 401
