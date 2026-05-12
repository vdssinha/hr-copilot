"""
In-process backend API tool implementations for the action agent.
All mutations go through service-layer validation — never direct SQL writes.
In a distributed deployment these would be httpx calls to the backend.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.employee import Employee

from app.services.leave_service import (
    apply_leave as _apply_leave,
    check_leave_balance as _check_leave_balance,
    approve_leave as _approve_leave,
    reject_leave as _reject_leave,
)
from app.services.ticket_service import (
    create_ticket as _create_ticket,
    assign_ticket as _assign_ticket,
)
from app.services.announcement_service import (
    create_announcement as _create_announcement,
)
from app.services.project_service import (
    assign_employee_to_project as _assign_employee_to_project,
)


# ─── Leave ────────────────────────────────────────────────────────────────────

def apply_leave(
    db: Session, user: Employee,
    leave_type: str, start_date: str, end_date: str,
    reason: str = "", is_half_day: bool = False,
    half_day_period: Optional[str] = None,
) -> dict:
    return _apply_leave(
        db=db, user=user,
        leave_type=leave_type, start_date=start_date, end_date=end_date,
        reason=reason, is_half_day=is_half_day, half_day_period=half_day_period,
    )


def check_leave_balance(db: Session, user: Employee, year: Optional[int] = None) -> dict:
    return _check_leave_balance(db=db, user=user, year=year)


def approve_leave(db: Session, actor: Employee, request_id: int) -> dict:
    return _approve_leave(db=db, actor=actor, request_id=request_id)


def reject_leave(db: Session, actor: Employee, request_id: int) -> dict:
    return _reject_leave(db=db, actor=actor, request_id=request_id)


# ─── Tickets ──────────────────────────────────────────────────────────────────

def create_ticket(
    db: Session, user: Employee,
    title: str, description: str = "",
    category: str = "OTHER", priority: str = "MEDIUM",
) -> dict:
    return _create_ticket(
        db=db, user=user,
        title=title, description=description,
        category=category, priority=priority,
    )


def assign_ticket(
    db: Session, actor: Employee,
    ticket_id: int, assignee_id: int,
    status: Optional[str] = None,
) -> dict:
    return _assign_ticket(
        db=db, actor=actor,
        ticket_id=ticket_id, assignee_id=assignee_id,
        status=status,
    )


# ─── Announcements ────────────────────────────────────────────────────────────

def create_announcement(
    db: Session, actor: Employee,
    title: str, content: str,
    category: str = "GENERAL", is_pinned: bool = False,
) -> dict:
    return _create_announcement(
        db=db, actor=actor,
        title=title, content=content,
        category=category, is_pinned=is_pinned,
    )


# ─── Projects ────────────────────────────────────────────────────────────────

def assign_employee_to_project(
    db: Session, actor: Employee,
    employee_id: int, project_id: int, role: str = "Member",
) -> dict:
    return _assign_employee_to_project(
        db=db, actor=actor,
        employee_id=employee_id, project_id=project_id, role=role,
    )
