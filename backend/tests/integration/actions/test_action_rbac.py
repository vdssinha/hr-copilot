"""
Integration: actions agent — RBAC enforcement and functional correctness.

Permission matrix:
  EMPLOYEE  → apply_leave, check_leave_balance, create_ticket
  MANAGER   → all employee actions + approve_leave, reject_leave,
              create_announcement, assign_ticket, assign_employee_to_project
  ADMIN     → all actions
"""
import requests
import pytest
from tests.integration.config import BASE_URL


def _chat_actions(message: str, token: str, timeout: int = 150) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/actions",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("success") is True
    return body["data"]


class TestLeaveActions:
    def test_employee_can_check_leave_balance(self, cc_employee_token):
        data = _chat_actions("What is my leave balance?", cc_employee_token)
        assert data["success"] is True

    def test_employee_can_apply_sick_leave(self, cc_employee_token):
        data = _chat_actions(
            "Apply sick leave from 2026-09-10 to 2026-09-11 reason: doctor visit",
            cc_employee_token,
        )
        assert data["action"] == "apply_leave"
        assert data["success"] is True

    def test_employee_cannot_approve_leave(self, cc_employee_token):
        """approve_leave is a manager-level action."""
        data = _chat_actions("Approve leave request 1", cc_employee_token)
        assert data["success"] is False
        assert "permission" in data["answer"].lower()

    def test_manager_can_check_leave_balance(self, cc_manager_token):
        data = _chat_actions("What is my remaining leave balance?", cc_manager_token)
        assert data["success"] is True


class TestAnnouncementActions:
    def test_employee_cannot_create_announcement(self, cc_employee_token):
        data = _chat_actions(
            "Create announcement: Company holiday on Friday",
            cc_employee_token,
        )
        assert data["success"] is False, \
            "Employee must not be able to create announcements"

    def test_manager_can_create_announcement(self, cc_manager_token):
        data = _chat_actions(
            "Create announcement titled 'Q3 update' with content 'Results are positive' category GENERAL",
            cc_manager_token,
        )
        assert data["action"] == "create_announcement"
        assert data["success"] is True


class TestActionsAuthEnforcement:
    def test_no_token_rejected(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/actions",
            json={"message": "check leave balance"},
            timeout=10,
        )
        assert resp.status_code == 401
