"""
Project REST endpoints.
All mutations delegate to project_service; no direct SQLAlchemy writes here.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.employee import Employee, EmployeeRole
from app.models.ai_audit_log import AIIntent, ActionStatus
from app.schemas.common import APIResponse
from app.services import project_service
from app.services.ai.core.audit import log_ai_interaction

router = APIRouter()

_PRIVILEGED = (
    EmployeeRole.MANAGER,
    EmployeeRole.HR,
    EmployeeRole.ADMIN,
    EmployeeRole.C_LEVEL,
)

_ADMIN_HR = (
    EmployeeRole.ADMIN,
    EmployeeRole.HR,
)


# ─── Request schemas ──────────────────────────────────────────────────────────

class AssignEmployeeToProjectRequest(BaseModel):
    project_id: int
    role: str = "Member"


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    status: str = "PLANNING"


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/employees/{employee_id}/projects", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def assign_employee_to_project(
    employee_id: int,
    body: AssignEmployeeToProjectRequest,
    current_user: Employee = Depends(require_role(*_PRIVILEGED)),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = project_service.assign_employee_to_project(
        db=db,
        actor=current_user,
        employee_id=employee_id,
        project_id=body.project_id,
        role=body.role,
    )
    if not result["success"]:
        log_ai_interaction(db, current_user,
                           f"Assign employee #{employee_id} to project #{body.project_id}",
                           AIIntent.HR_ACTION, ActionStatus.ERROR, tool_name="assign_employee_to_project")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    log_ai_interaction(db, current_user,
                       f"Assign employee #{employee_id} to project #{body.project_id} as {body.role}",
                       AIIntent.HR_ACTION, ActionStatus.SUCCESS, tool_name="assign_employee_to_project",
                       records_accessed=[str(employee_id), str(body.project_id)])
    return APIResponse.ok(result["data"])


@router.get("/projects/my", response_model=APIResponse)
def my_projects(
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = project_service.view_own_projects(db=db, user=current_user)
    return APIResponse.ok(result["data"])


@router.get("/projects", response_model=APIResponse)
def list_projects(
    current_user: Employee = Depends(require_role(*_PRIVILEGED)),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = project_service.list_projects(db=db, actor=current_user)
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=result["error"])
    return APIResponse.ok(result["data"])


@router.post("/projects", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest,
    current_user: Employee = Depends(require_role(*_ADMIN_HR)),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = project_service.create_project(
        db=db,
        actor=current_user,
        name=body.name,
        description=body.description,
        status=body.status,
    )
    if not result["success"]:
        log_ai_interaction(db, current_user, f"Create project: {body.name}",
                           AIIntent.HR_ACTION, ActionStatus.ERROR, tool_name="create_project")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    log_ai_interaction(db, current_user, f"Create project: {body.name}",
                       AIIntent.HR_ACTION, ActionStatus.SUCCESS, tool_name="create_project",
                       records_accessed=[str(result["data"].get("id"))])
    return APIResponse.ok(result["data"])


@router.get("/projects/employees", response_model=APIResponse)
def project_employees(
    skill: Optional[str] = Query(default=None, description="Filter employees by skill name"),
    current_user: Employee = Depends(require_role(*_PRIVILEGED)),
    db: Session = Depends(get_db),
) -> APIResponse:
    if skill:
        result = project_service.search_employees_by_skill(db=db, actor=current_user, skill_name=skill)
    else:
        result = project_service.check_project_assignments(db=db, actor=current_user)
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=result["error"])
    return APIResponse.ok(result["data"])
