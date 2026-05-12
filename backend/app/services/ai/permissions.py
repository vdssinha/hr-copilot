from app.models.employee import Employee, EmployeeRole

_EMPLOYEE_BASE = frozenset({
    "apply_leave", "check_leave_balance", "get_my_leaves",
    "create_ticket", "check_ticket_status", "view_own_projects",
})

_MANAGER_EXTRA = frozenset({
    "approve_leave", "reject_leave", "list_pending_approvals",
    "assign_ticket", "search_employees_by_skill",
    "check_project_assignments", "create_announcement",
    "assign_employee_to_project",
})

_ROLE_PERMISSIONS: dict[EmployeeRole, frozenset[str]] = {
    EmployeeRole.EMPLOYEE: _EMPLOYEE_BASE,
    EmployeeRole.MARKETING: _EMPLOYEE_BASE,
    EmployeeRole.MANAGER: _EMPLOYEE_BASE | _MANAGER_EXTRA,
    EmployeeRole.HR: _EMPLOYEE_BASE | _MANAGER_EXTRA,
    EmployeeRole.C_LEVEL: _EMPLOYEE_BASE | _MANAGER_EXTRA,
    EmployeeRole.ADMIN: _EMPLOYEE_BASE | _MANAGER_EXTRA | frozenset({"create_project"}),
}


def can_perform(user: Employee, action: str) -> bool:
    return action in _ROLE_PERMISSIONS.get(user.role, frozenset())


def allowed_actions(user: Employee) -> frozenset[str]:
    return _ROLE_PERMISSIONS.get(user.role, frozenset())
