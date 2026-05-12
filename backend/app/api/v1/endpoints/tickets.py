"""
Ticket REST endpoints.
All mutations delegate to ticket_service; no direct SQLAlchemy writes here.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.employee import Employee, EmployeeRole
from app.schemas.common import APIResponse
from app.services import ticket_service

router = APIRouter()

_PRIVILEGED = (
    EmployeeRole.MANAGER,
    EmployeeRole.HR,
    EmployeeRole.ADMIN,
    EmployeeRole.C_LEVEL,
)


# ─── Request schemas ──────────────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    title: str
    description: str = ""
    category: str = "OTHER"
    priority: str = "MEDIUM"


class UpdateTicketRequest(BaseModel):
    assignee_id: int
    status: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    body: CreateTicketRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = ticket_service.create_ticket(
        db=db,
        user=current_user,
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return APIResponse.ok(result["data"])


@router.patch("/{ticket_id}", response_model=APIResponse)
def update_ticket(
    ticket_id: int,
    body: UpdateTicketRequest,
    current_user: Employee = Depends(require_role(*_PRIVILEGED)),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = ticket_service.assign_ticket(
        db=db,
        actor=current_user,
        ticket_id=ticket_id,
        assignee_id=body.assignee_id,
        status=body.status,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return APIResponse.ok(result["data"])


@router.get("/my", response_model=APIResponse)
def my_tickets(
    limit: int = 20,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse:
    result = ticket_service.check_ticket_status(db=db, user=current_user, limit=limit)
    return APIResponse.ok(result["data"])
