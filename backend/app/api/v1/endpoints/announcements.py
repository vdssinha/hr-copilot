"""
Announcement REST endpoints.
All mutations delegate to announcement_service; no direct SQLAlchemy writes here.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.employee import Employee, EmployeeRole
from app.models.ai_audit_log import AIIntent, ActionStatus
from app.schemas.common import APIResponse
from app.services import announcement_service
from app.services.ai.core.audit import log_ai_interaction

router = APIRouter()

_PRIVILEGED = (
    EmployeeRole.MANAGER,
    EmployeeRole.HR,
    EmployeeRole.ADMIN,
    EmployeeRole.C_LEVEL,
)


# ─── Request schemas ──────────────────────────────────────────────────────────

class CreateAnnouncementRequest(BaseModel):
    title: str
    content: str
    category: str = "GENERAL"
    is_pinned: bool = False


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=APIResponse)
def list_announcements(
    limit: int = 50,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = announcement_service.list_announcements(db=db, limit=limit)
    return APIResponse.ok(result["data"])


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_announcement(
    body: CreateAnnouncementRequest,
    current_user: Employee = Depends(require_role(*_PRIVILEGED)),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = announcement_service.create_announcement(
        db=db,
        actor=current_user,
        title=body.title,
        content=body.content,
        category=body.category,
        is_pinned=body.is_pinned,
    )
    if not result["success"]:
        log_ai_interaction(db, current_user, f"Create announcement: {body.title}",
                           AIIntent.HR_ACTION, ActionStatus.ERROR, tool_name="create_announcement")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    log_ai_interaction(db, current_user, f"Create announcement: {body.title}",
                       AIIntent.HR_ACTION, ActionStatus.SUCCESS, tool_name="create_announcement",
                       records_accessed=[str(result["data"].get("id"))])
    return APIResponse.ok(result["data"])
