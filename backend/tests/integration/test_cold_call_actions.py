"""Cold-call: actions endpoint RBAC and functionality tests (live backend)."""
import requests
import pytest
from tests.integration.cold_call_config import BASE_URL
from tests.integration.cold_call_conftest import (  # noqa: F401
    cc_admin_token, cc_manager_token, cc_employee_token,
)


def _action(message: str, token: str, timeout: int = 30) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/actions",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("success") is True
    return body["data"]


class TestLeaveActions:
    def test_employee_can_check_leave_balance(self, cc_employee_token):
        data = _action("What is my leave balance?", cc_employee_token)
        assert "action" in data
        assert data["success"] is True

    def test_employee_apply_leave(self, cc_employee_token):
        data = _action(
            "Apply sick leave from 2026-09-01 to 2026-09-02 reason: doctor visit",
            cc_employee_token,
        )
        assert data["action"] == "apply_leave"
        assert data["success"] is True

    def test_employee_cannot_approve_leave(self, cc_employee_token):
        """Employees don't have approve_leave permission."""
        data = _action("Approve leave request 1", cc_employee_token)
        assert data["success"] is False
        assert "permission" in data["answer"].lower()

    def test_manager_can_check_balance(self, cc_manager_token):
        data = _action("What is my remaining leave balance?", cc_manager_token)
        assert data["success"] is True


class TestAnnouncementActions:
    def test_employee_cannot_create_announcement(self, cc_employee_token):
        data = _action(
            "Create announcement: Company holiday on Friday",
            cc_employee_token,
        )
        assert data["success"] is False

    def test_manager_can_create_announcement(self, cc_manager_token):
        data = _action(
            "Create announcement titled 'Team sync' with content 'Weekly sync moved to 3pm' category GENERAL",
            cc_manager_token,
        )
        assert data["action"] == "create_announcement"
        assert data["success"] is True


class TestActionsAuth:
    def test_no_token_rejected(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/actions",
            json={"message": "check leave balance"},
            timeout=10,
        )
        assert resp.status_code == 401
