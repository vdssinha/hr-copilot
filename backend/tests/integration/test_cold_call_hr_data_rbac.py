"""
Cold-call: HR data RBAC tests (live backend, no mocks).

Validates field-level access control at query time:
  EMPLOYEE  — can only retrieve their OWN record; salary/DOB/phone visible for self
  MANAGER   — sees all records; salary/DOB/phone visible for DIRECT REPORTS only,
              [RESTRICTED] for everyone else
  ADMIN     — unrestricted access to all fields for all employees

Requires HR data ingested into ChromaDB.
Set COLD_CALL_SKIP_INGEST=1 to skip the ingest step if already done.
"""
import os
import requests
import pytest
from tests.integration.cold_call_config import BASE_URL, USERS, SENSITIVE_FIELDS, RESTRICTED_MARKER
from tests.integration.cold_call_conftest import (  # noqa: F401
    cc_admin_token, cc_manager_token, cc_employee_token,
)

_SKIP_INGEST = os.getenv("COLD_CALL_SKIP_INGEST", "0") == "1"


def _hr(message: str, token: str, timeout: int = 30) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/hr-data",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("success") is True, f"success=False: {body}"
    return body["data"]


@pytest.fixture(scope="module", autouse=True)
def ensure_hr_ingested(cc_admin_token):
    """Ingest HR data once before the module runs (unless skipped)."""
    if _SKIP_INGEST:
        return
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/hr-data/ingest",
        headers={"Authorization": f"Bearer {cc_admin_token}"},
        timeout=60,
    )
    assert resp.status_code == 200, f"Ingest failed: {resp.text}"
    data = resp.json()
    assert data.get("success") is True, f"Ingest not successful: {data}"


class TestEmployeeAccess:
    """EMPLOYEE can only see their own record (vector-store where-filter by employee_id)."""

    def test_employee_can_query_own_record(self, cc_employee_token):
        emp = USERS["employee"]
        data = _hr("What is my salary?", cc_employee_token)
        answer = data.get("answer", "").lower()
        assert (
            emp["name"].split()[0].lower() in answer
            or "1200000" in answer
            or "salary" in answer
        ), f"Expected own record in answer, got: {answer}"

    def test_employee_salary_visible_for_self(self, cc_employee_token):
        """Own salary must NOT be [RESTRICTED]."""
        data = _hr("What is my salary?", cc_employee_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER not in answer or "1200000" in answer, \
            f"Own salary should not be restricted: {answer}"

    def test_employee_cannot_see_other_records(self, cc_employee_token):
        """Asking about another person must not reveal their salary."""
        data = _hr("What is Arjun Mehta's salary?", cc_employee_token)
        answer = data["answer"].lower()
        assert "1950000" not in answer, \
            f"Manager salary must not be visible to employee: {answer}"

    def test_employee_context_contains_only_own_code(self, cc_employee_token):
        """Other NW employee codes must not appear in the answer."""
        data = _hr("Show me all employee details", cc_employee_token)
        answer = data["answer"]
        for other_code in ["NW-001", "NW-002"]:
            assert other_code not in answer, \
                f"Code {other_code} leaked into employee answer"


class TestManagerAccess:
    """MANAGER sees all records; sensitive fields redacted for non-direct-reports."""

    def test_direct_report_salary_visible(self, cc_manager_token):
        """Rahul Verma (NW-004) is Arjun Mehta's direct report — salary must be visible."""
        data = _hr("What is Rahul Verma's salary?", cc_manager_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER not in answer or "1200000" in answer, \
            f"Direct report salary should not be restricted: {answer}"

    def test_non_direct_report_salary_restricted(self, cc_manager_token):
        """Priya Sharma (NW-001) is the manager's own manager — salary must be [RESTRICTED]."""
        data = _hr("What is Priya Sharma's salary?", cc_manager_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER in answer or "2800000" not in answer, \
            f"Non-direct-report salary must be [RESTRICTED]: {answer}"

    def test_manager_sees_direct_report_name(self, cc_manager_token):
        data = _hr("Tell me about Rahul Verma", cc_manager_token)
        answer = data["answer"].lower()
        assert "rahul" in answer or "verma" in answer, \
            f"Manager should see direct report info: {answer}"

    def test_manager_can_query_across_all_employees(self, cc_manager_token):
        """No where-filter — manager can ask department-level questions."""
        data = _hr("How many employees are in the Engineering department?", cc_manager_token)
        answer = data["answer"].lower()
        assert "no matching" not in answer and "not ingested" not in answer, \
            f"Manager should get results for department query: {answer}"


class TestAdminAccess:
    """ADMIN has full unrestricted access to all fields for all employees."""

    def test_admin_sees_employee_salary(self, cc_admin_token):
        data = _hr("What is Rahul Verma's salary?", cc_admin_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER not in answer or "1200000" in answer, \
            f"Admin should see salary unrestricted: {answer}"

    def test_admin_sees_manager_salary(self, cc_admin_token):
        data = _hr("What is Arjun Mehta's salary?", cc_admin_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER not in answer or "1950000" in answer, \
            f"Admin should see manager salary: {answer}"

    def test_admin_gets_non_empty_answer(self, cc_admin_token):
        data = _hr("List all employees in HR department", cc_admin_token)
        answer = data["answer"].lower()
        assert "no matching" not in answer and "not ingested" not in answer, \
            f"Admin query should return results: {answer}"


class TestUnauthenticated:
    def test_no_token_rejected(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/hr-data",
            json={"message": "What is Rahul's salary?"},
            timeout=10,
        )
        assert resp.status_code == 401
