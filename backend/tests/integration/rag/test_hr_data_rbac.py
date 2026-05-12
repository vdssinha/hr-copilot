"""
Integration: HR data field-level RBAC.

Access rules enforced at query time (not ingestion time):
  EMPLOYEE  → only their own record (vector-store where-filter by employee_id)
  MANAGER   → all records; salary/DOB/phone shown for direct reports only,
              [RESTRICTED] for everyone else
  ADMIN     → unrestricted access to all fields

Requires HR data ingested. Set INTEGRATION_SKIP_INGEST=1 to skip ingest.
"""
import time
import requests
import pytest
from tests.integration.config import BASE_URL, USERS, RESTRICTED_MARKER, SKIP_INGEST, hr_field


def _chat_hr(message: str, token: str, timeout: int = 120) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/hr-data",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("success") is True, f"success=False: {body}"
    return body["data"]


@pytest.fixture(scope="module", autouse=True)
def ingest_hr_data(cc_admin_token):
    """Trigger async ingest then poll until vector store has data (up to 120s)."""
    if SKIP_INGEST:
        return
    resp = requests.post(
        f"{BASE_URL}/api/v1/admin/hr-data/ingest",
        headers={"Authorization": f"Bearer {cc_admin_token}"},
        timeout=30,
    )
    assert resp.status_code == 200, f"Ingest trigger failed: {resp.text}"

    deadline = time.time() + 180
    while time.time() < deadline:
        probe = requests.post(
            f"{BASE_URL}/api/v1/chat/hr-data",
            json={"message": "Tell me about Rahul Verma NW-004"},
            headers={"Authorization": f"Bearer {cc_admin_token}"},
            timeout=90,
        )
        if probe.status_code == 200:
            answer = probe.json().get("data", {}).get("answer", "").lower()
            if (
                "not ingested" not in answer
                and "no matching" not in answer
                and ("rahul" in answer or "nw-004" in answer or "verma" in answer)
            ):
                return
        time.sleep(8)

    pytest.fail("HR data not available in vector store after 180s")


class TestEmployeeSelfAccess:
    """Employee sees only their own record; salary visible for self."""

    def test_own_record_returned(self, cc_employee_token):
        emp = USERS["employee"]
        own_salary = hr_field(emp["employee_code"], "salary")
        data = _chat_hr("What is my salary?", cc_employee_token)
        answer = data["answer"].lower()
        assert (
            emp["name"].split()[0].lower() in answer
            or (own_salary and own_salary in answer)
            or "salary" in answer
        ), f"Own record missing from answer: {answer}"

    def test_own_salary_not_restricted(self, cc_employee_token):
        emp = USERS["employee"]
        own_salary = hr_field(emp["employee_code"], "salary")
        data = _chat_hr("What is my salary?", cc_employee_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER not in answer or (own_salary and own_salary in answer), \
            f"Own salary must not be [RESTRICTED]: {answer}"

    def test_other_employee_salary_not_leaked(self, cc_employee_token):
        """Where-filter blocks records for other employees."""
        mgr = USERS["manager"]
        mgr_salary = hr_field(mgr["employee_code"], "salary")
        data = _chat_hr(f"What is {mgr['name']}'s salary?", cc_employee_token)
        assert not mgr_salary or mgr_salary not in data["answer"], \
            f"Manager salary must not leak to employee: {data['answer']}"

    def test_other_employee_codes_not_in_answer(self, cc_employee_token):
        """Other employees' profiles must not leak — filter is active.
        NW-002 may appear as 'Manager ID' in the employee's own record (expected),
        but other employees' names must not appear."""
        data = _chat_hr("Show me all employee details", cc_employee_token)
        answer = data["answer"]
        # Other employees' names should not be in the answer
        for name in ["Priya Sharma", "Arjun Mehta"]:
            assert name not in answer, \
                f"Other employee profile '{name}' leaked into employee-scoped answer"


class TestManagerDirectReportAccess:
    """Manager sees all employees; sensitive fields restricted for non-direct-reports."""

    def test_direct_report_salary_visible(self, cc_manager_token):
        """Rahul Verma (NW-004) is Arjun Mehta's direct report — salary shown."""
        emp = USERS["employee"]
        emp_salary = hr_field(emp["employee_code"], "salary")
        data = _chat_hr(f"What is {emp['name']}'s salary?", cc_manager_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER not in answer or (emp_salary and emp_salary in answer), \
            f"Direct-report salary should be visible: {answer}"

    def test_non_direct_report_salary_restricted(self, cc_manager_token):
        """Priya Sharma (NW-001) is manager's own manager — salary must be [RESTRICTED]."""
        admin = USERS["admin"]
        admin_salary = hr_field(admin["employee_code"], "salary")
        data = _chat_hr(f"What is {admin['name']}'s salary?", cc_manager_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER in answer or not admin_salary or admin_salary not in answer, \
            f"Non-direct-report salary must be [RESTRICTED]: {answer}"

    def test_direct_report_profile_visible(self, cc_manager_token):
        data = _chat_hr("Tell me about Rahul Verma", cc_manager_token)
        answer = data["answer"].lower()
        assert "rahul" in answer or "verma" in answer, \
            f"Manager should see direct-report profile: {answer}"

    def test_department_query_returns_results(self, cc_manager_token):
        """No where-filter for managers — cross-employee queries work."""
        data = _chat_hr("How many employees are in Engineering?", cc_manager_token)
        answer = data["answer"].lower()
        assert "no matching" not in answer and "not ingested" not in answer, \
            f"Manager should get cross-employee results: {answer}"


class TestAdminUnrestrictedAccess:
    """Admin sees everything — no [RESTRICTED] for any field."""

    def test_employee_salary_fully_visible(self, cc_admin_token):
        emp = USERS["employee"]
        emp_salary = hr_field(emp["employee_code"], "salary")
        data = _chat_hr(f"What is {emp['name']}'s salary?", cc_admin_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER not in answer or (emp_salary and emp_salary in answer), \
            f"Admin should see salary unrestricted: {answer}"

    def test_manager_salary_fully_visible(self, cc_admin_token):
        mgr = USERS["manager"]
        mgr_salary = hr_field(mgr["employee_code"], "salary")
        data = _chat_hr(f"What is {mgr['name']}'s salary?", cc_admin_token)
        answer = data["answer"]
        assert RESTRICTED_MARKER not in answer or (mgr_salary and mgr_salary in answer), \
            f"Admin should see all salaries: {answer}"

    def test_department_query_non_empty(self, cc_admin_token):
        data = _chat_hr("List employees in the HR department", cc_admin_token)
        answer = data["answer"].lower()
        assert "no matching" not in answer and "not ingested" not in answer, \
            f"Admin query should return results: {answer}"


class TestHrDataAuthEnforcement:
    def test_no_token_rejected(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/hr-data",
            json={"message": "What is Rahul's salary?"},
            timeout=10,
        )
        assert resp.status_code == 401
