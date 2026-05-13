"""
Leave REST endpoints.
All mutations delegate to leave_service; no direct SQLAlchemy writes here.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.employee import Employee, EmployeeRole
from app.models.ai_audit_log import AIIntent, ActionStatus
from app.schemas.common import APIResponse
from app.services import leave_service
from app.services.ai.audit import log_ai_interaction

router = APIRouter()

_APPROVERS = (
    EmployeeRole.MANAGER,
    EmployeeRole.HR,
    EmployeeRole.ADMIN,
    EmployeeRole.C_LEVEL,
)


# ─── Request schemas ──────────────────────────────────────────────────────────

class CreateLeaveRequest(BaseModel):
    leave_type: str
    start_date: str
    end_date: str
    reason: str = ""
    is_half_day: bool = False
    half_day_period: Optional[str] = None


class UpdateLeaveRequest(BaseModel):
    action: str  # "approve" or "reject"


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/requests", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_leave_request(
    body: CreateLeaveRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = leave_service.apply_leave(
        db=db,
        user=current_user,
        leave_type=body.leave_type,
        start_date=body.start_date,
        end_date=body.end_date,
        reason=body.reason,
        is_half_day=body.is_half_day,
        half_day_period=body.half_day_period,
    )
    if not result["success"]:
        log_ai_interaction(db, current_user, f"Apply {body.leave_type} leave {body.start_date}→{body.end_date}",
                           AIIntent.HR_ACTION, ActionStatus.ERROR, tool_name="apply_leave")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    log_ai_interaction(db, current_user, f"Apply {body.leave_type} leave {body.start_date}→{body.end_date}",
                       AIIntent.HR_ACTION, ActionStatus.SUCCESS, tool_name="apply_leave")
    return APIResponse.ok(result["data"])


@router.patch("/requests/{request_id}", response_model=APIResponse)
def update_leave_request(
    request_id: int,
    body: UpdateLeaveRequest,
    current_user: Employee = Depends(require_role(*_APPROVERS)),
    db: Session = Depends(get_db),
) -> APIResponse:
    action = body.action.lower()
    if action == "approve":
        result = leave_service.approve_leave(db=db, actor=current_user, request_id=request_id)
    elif action == "reject":
        result = leave_service.reject_leave(db=db, actor=current_user, request_id=request_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be 'approve' or 'reject'",
        )
    tool = f"{action}_leave"
    if not result["success"]:
        log_ai_interaction(db, current_user, f"{action.title()} leave request #{request_id}",
                           AIIntent.HR_ACTION, ActionStatus.ERROR, tool_name=tool)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    log_ai_interaction(db, current_user, f"{action.title()} leave request #{request_id}",
                       AIIntent.HR_ACTION, ActionStatus.SUCCESS, tool_name=tool,
                       records_accessed=[str(request_id)])
    return APIResponse.ok(result["data"])


@router.get("/requests/my", response_model=APIResponse)
def my_leaves(
    limit: int = 20,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = leave_service.get_my_leaves(db=db, user=current_user, limit=limit)
    return APIResponse.ok(result["data"])


@router.get("/requests/pending", response_model=APIResponse)
def pending_approvals(
    current_user: Employee = Depends(require_role(*_APPROVERS)),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = leave_service.list_pending_approvals(db=db, actor=current_user)
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=result["error"])
    return APIResponse.ok(result["data"])
