"""
Project business logic — single source of truth for all project operations.
Called by both api_tools.py (AI agent path) and REST endpoints.
"""
from sqlalchemy.orm import Session

from app.models.employee import Employee, EmployeeRole
from app.models.project import Project, EmployeeProject, ProjectStatus
from app.models.skill import Skill, EmployeeSkill

_PRIVILEGED_ROLES = {EmployeeRole.MANAGER, EmployeeRole.ADMIN, EmployeeRole.HR, EmployeeRole.C_LEVEL}


def assign_employee_to_project(
    db: Session,
    actor: Employee,
    employee_id: int,
    project_id: int,
    role: str = "Member",
) -> dict:
    if actor.role == EmployeeRole.EMPLOYEE:
        return {"success": False, "error": "You do not have permission to assign employees to projects."}

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"success": False, "error": f"Project #{project_id} not found."}

    existing = db.query(EmployeeProject).filter(
        EmployeeProject.employee_id == employee_id,
        EmployeeProject.project_id == project_id,
        EmployeeProject.is_active == True,  # noqa: E712
    ).first()
    if existing:
        return {"success": False, "error": "Employee is already assigned to this project."}

    ep = EmployeeProject(employee_id=employee_id, project_id=project_id, role=role)
    db.add(ep)
    db.commit()
    return {
        "success": True,
        "data": {"employee_id": employee_id, "project_id": project_id, "role": role},
    }


def view_own_projects(db: Session, user: Employee) -> dict:
    """Returns own active project assignments."""
    assignments = (
        db.query(EmployeeProject)
        .filter(
            EmployeeProject.employee_id == user.id,
            EmployeeProject.is_active == True,  # noqa: E712
        )
        .all()
    )
    data = [
        {
            "project_id": a.project_id,
            "project_name": a.project.name if a.project else None,
            "role": a.role,
            "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
        }
        for a in assignments
    ]
    return {"success": True, "data": data}


def search_employees_by_skill(db: Session, actor: Employee, skill_name: str) -> dict:
    """MANAGER/ADMIN/HR/C_LEVEL only. Searches employees by skill name (case-insensitive)."""
    if actor.role not in _PRIVILEGED_ROLES:
        return {"success": False, "error": "You do not have permission to search employees by skill."}

    results = (
        db.query(EmployeeSkill)
        .join(Skill, EmployeeSkill.skill_id == Skill.id)
        .filter(Skill.name.ilike(f"%{skill_name}%"))
        .all()
    )
    data = [
        {
            "employee_id": es.employee_id,
            "name": es.employee.name if es.employee else None,
            "email": es.employee.email if es.employee else None,
            "job_title": es.employee.job_title if es.employee else None,
            "skill_name": es.skill.name if es.skill else None,
            "proficiency": es.proficiency.value,
        }
        for es in results
    ]
    return {"success": True, "data": data}


def check_project_assignments(db: Session, actor: Employee) -> dict:
    """
    MANAGER: projects that have at least one employee reporting to actor.
    HR/ADMIN/C_LEVEL: all active projects with their employees.
    """
    if actor.role not in _PRIVILEGED_ROLES:
        return {"success": False, "error": "You do not have permission to view project assignments."}

    if actor.role == EmployeeRole.MANAGER:
        # projects where any assigned employee reports to this manager
        from app.models.employee import Employee as Emp
        report_ids = [e.id for e in db.query(Emp).filter(Emp.manager_id == actor.id).all()]
        if not report_ids:
            return {"success": True, "data": []}

        eps = (
            db.query(EmployeeProject)
            .filter(
                EmployeeProject.employee_id.in_(report_ids),
                EmployeeProject.is_active == True,  # noqa: E712
            )
            .all()
        )
    else:
        eps = (
            db.query(EmployeeProject)
            .filter(EmployeeProject.is_active == True)  # noqa: E712
            .all()
        )

    # group by project
    projects: dict[int, dict] = {}
    for ep in eps:
        pid = ep.project_id
        if pid not in projects:
            projects[pid] = {
                "project_id": pid,
                "project_name": ep.project.name if ep.project else None,
                "employees": [],
            }
        projects[pid]["employees"].append({
            "employee_id": ep.employee_id,
            "name": ep.employee.name if ep.employee else None,
            "role": ep.role,
        })

    return {"success": True, "data": list(projects.values())}


def list_projects(db: Session, actor: Employee) -> dict:
    """MANAGER/HR/ADMIN/C_LEVEL: list all projects."""
    if actor.role not in _PRIVILEGED_ROLES:
        return {"success": False, "error": "You do not have permission to list all projects."}

    projects = db.query(Project).order_by(Project.created_at.desc()).limit(50).all()
    data = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "status": p.status.value,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "end_date": p.end_date.isoformat() if p.end_date else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in projects
    ]
    return {"success": True, "data": data}


def create_project(
    db: Session,
    actor: Employee,
    name: str,
    description: str = "",
    status: str = "PLANNING",
) -> dict:
    """ADMIN/HR only. Creates a new Project record."""
    allowed = {EmployeeRole.ADMIN, EmployeeRole.HR}
    if actor.role not in allowed:
        return {"success": False, "error": "Only ADMIN or HR can create projects."}

    try:
        ps = ProjectStatus[status.upper()]
    except KeyError:
        ps = ProjectStatus.PLANNING

    existing = db.query(Project).filter(Project.name == name).first()
    if existing:
        return {"success": False, "error": f"A project named '{name}' already exists."}

    project = Project(name=name, description=description, status=ps)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"success": True, "data": {"id": project.id, "name": project.name, "status": ps.value}}
