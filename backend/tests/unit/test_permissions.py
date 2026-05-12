"""
Unit tests for permissions — RBAC action permission checks.
No DB or LLM needed; Employee instances built with minimal fields.
"""
import pytest
from unittest.mock import MagicMock
from app.models.employee import EmployeeRole
from app.services.ai.permissions import can_perform, allowed_actions


def _emp(role: EmployeeRole):
    emp = MagicMock()
    emp.role = role
    return emp


EMPLOYEE = _emp(EmployeeRole.EMPLOYEE)
MANAGER = _emp(EmployeeRole.MANAGER)
ADMIN = _emp(EmployeeRole.ADMIN)


# ─── EMPLOYEE role ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("action", [
    "apply_leave", "check_leave_balance", "get_my_leaves",
    "create_ticket", "check_ticket_status", "view_own_projects",
])
def test_employee_can_perform_basic_actions(action):
    assert can_perform(EMPLOYEE, action) is True


@pytest.mark.parametrize("action", [
    "approve_leave", "reject_leave", "list_pending_approvals",
    "assign_ticket", "create_announcement", "assign_employee_to_project",
    "search_employees_by_skill", "check_project_assignments",
])
def test_employee_cannot_perform_manager_actions(action):
    assert can_perform(EMPLOYEE, action) is False


# ─── MANAGER role ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("action", [
    "apply_leave", "check_leave_balance", "get_my_leaves",
    "create_ticket", "check_ticket_status", "view_own_projects",
    "approve_leave", "reject_leave", "list_pending_approvals",
    "assign_ticket", "create_announcement", "assign_employee_to_project",
    "search_employees_by_skill", "check_project_assignments",
])
def test_manager_can_perform_all_manager_actions(action):
    assert can_perform(MANAGER, action) is True


def test_manager_cannot_create_project():
    assert can_perform(MANAGER, "create_project") is False


# ─── ADMIN role ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("action", [
    "apply_leave", "check_leave_balance", "get_my_leaves",
    "create_ticket", "check_ticket_status", "view_own_projects",
    "approve_leave", "reject_leave", "list_pending_approvals",
    "assign_ticket", "create_announcement", "assign_employee_to_project",
    "search_employees_by_skill", "check_project_assignments", "create_project",
])
def test_admin_can_perform_all_actions(action):
    assert can_perform(ADMIN, action) is True


# ─── Unknown role ─────────────────────────────────────────────────────────────

def test_unknown_role_cannot_perform_anything():
    unknown = MagicMock()
    unknown.role = "UNKNOWN_ROLE"
    assert can_perform(unknown, "apply_leave") is False


# ─── allowed_actions ─────────────────────────────────────────────────────────

def test_allowed_actions_employee_subset():
    actions = allowed_actions(EMPLOYEE)
    assert "apply_leave" in actions
    assert "approve_leave" not in actions
    assert "create_announcement" not in actions


def test_allowed_actions_manager_superset_of_employee():
    emp_actions = allowed_actions(EMPLOYEE)
    mgr_actions = allowed_actions(MANAGER)
    assert emp_actions.issubset(mgr_actions)


def test_allowed_actions_admin_superset_of_manager():
    mgr_actions = allowed_actions(MANAGER)
    adm_actions = allowed_actions(ADMIN)
    assert mgr_actions.issubset(adm_actions)


def test_allowed_actions_returns_frozenset():
    assert isinstance(allowed_actions(EMPLOYEE), frozenset)
