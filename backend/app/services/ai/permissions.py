from app.models.employee import Employee, EmployeeRole

_ROLE_PERMISSIONS: dict[EmployeeRole, frozenset[str]] = {
    EmployeeRole.EMPLOYEE: frozenset({
        "apply_leave", "check_leave_balance", "create_ticket",
        "check_ticket_status", "view_own_projects",
    }),
    EmployeeRole.MANAGER: frozenset({
        "apply_leave", "check_leave_balance", "create_ticket",
        "check_ticket_status", "view_own_projects",
        "approve_leave", "reject_leave", "assign_ticket",
        "view_team_leave", "search_employees_by_skill",
        "check_project_assignments", "create_announcement",
        "assign_employee_to_project",
    }),
    EmployeeRole.ADMIN: frozenset({
        "apply_leave", "check_leave_balance", "create_ticket",
        "check_ticket_status", "view_own_projects",
        "approve_leave", "reject_leave", "assign_ticket",
        "view_team_leave", "search_employees_by_skill",
        "check_project_assignments", "create_announcement",
        "assign_employee_to_project", "create_project",
    }),
}


def can_perform(user: Employee, action: str) -> bool:
    return action in _ROLE_PERMISSIONS.get(user.role, frozenset())


def allowed_actions(user: Employee) -> frozenset[str]:
    return _ROLE_PERMISSIONS.get(user.role, frozenset())
