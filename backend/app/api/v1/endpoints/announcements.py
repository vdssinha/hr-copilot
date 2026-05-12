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
from app.schemas.common import APIResponse
from app.services import announcement_service

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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return APIResponse.ok(result["data"])
