"""
In-process backend API tool implementations for the action agent.
All mutations go through service-layer validation — never direct SQL writes.
In a distributed deployment these would be httpx calls to the backend.
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models.employee import Employee, EmployeeRole
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus, LeaveBalance, HalfDayPeriod
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus
from app.models.announcement import Announcement, AnnouncementCategory
from app.models.project import Project, EmployeeProject, ProjectStatus


# ─── Leave ────────────────────────────────────────────────────────────────────

def apply_leave(
    db: Session, user: Employee,
    leave_type: str, start_date: str, end_date: str,
    reason: str = "", is_half_day: bool = False,
    half_day_period: Optional[str] = None,
) -> dict:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (ValueError, TypeError):
        return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}

    if start > end:
        return {"success": False, "error": "Start date must be before or equal to end date."}

    try:
        lt = LeaveType[leave_type.upper()]
    except KeyError:
        return {"success": False, "error": f"Unknown leave type: {leave_type}. Use CASUAL, SICK, ANNUAL, or UNPAID."}

    hp = None
    if is_half_day and half_day_period:
        try:
            hp = HalfDayPeriod[half_day_period.upper()]
        except KeyError:
            pass

    req = LeaveRequest(
        employee_id=user.id,
        leave_type=lt,
        start_date=start,
        end_date=end,
        reason=reason,
        is_half_day=is_half_day,
        half_day_period=hp,
        status=LeaveStatus.PENDING,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {
        "success": True,
        "data": {
            "id": req.id,
            "leave_type": lt.value,
            "start_date": start_date,
            "end_date": end_date,
            "status": "PENDING",
            "message": f"Leave request submitted. Status: Pending approval.",
        },
    }


def check_leave_balance(db: Session, user: Employee, year: Optional[int] = None) -> dict:
    year = year or datetime.utcnow().year
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == user.id,
        LeaveBalance.year == year,
    ).first()
    if not balance:
        return {"success": False, "error": f"No leave balance found for {year}."}
    return {
        "success": True,
        "data": {
            "year": year,
            "casual": {"total": balance.casual_leave_total, "used": balance.casual_leave_used,
                       "remaining": balance.casual_leave_total - balance.casual_leave_used},
            "sick": {"total": balance.sick_leave_total, "used": balance.sick_leave_used,
                     "remaining": balance.sick_leave_total - balance.sick_leave_used},
            "annual": {"total": balance.annual_leave_total, "used": balance.annual_leave_used,
                       "remaining": balance.annual_leave_total - balance.annual_leave_used},
        },
    }


def approve_leave(db: Session, actor: Employee, request_id: int) -> dict:
    req = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not req:
        return {"success": False, "error": f"Leave request #{request_id} not found."}
    if req.status != LeaveStatus.PENDING:
        return {"success": False, "error": f"Request is already {req.status.value}."}
    if actor.role == EmployeeRole.EMPLOYEE:
        return {"success": False, "error": "You do not have permission to approve leave requests."}

    req.status = LeaveStatus.APPROVED
    req.approved_by_id = actor.id
    req.approved_at = datetime.utcnow()
    db.commit()
    return {"success": True, "data": {"id": req.id, "status": "APPROVED"}}


def reject_leave(db: Session, actor: Employee, request_id: int) -> dict:
    req = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not req:
        return {"success": False, "error": f"Leave request #{request_id} not found."}
    if req.status != LeaveStatus.PENDING:
        return {"success": False, "error": f"Request is already {req.status.value}."}
    if actor.role == EmployeeRole.EMPLOYEE:
        return {"success": False, "error": "You do not have permission to reject leave requests."}

    req.status = LeaveStatus.REJECTED
    req.approved_by_id = actor.id
    req.approved_at = datetime.utcnow()
    db.commit()
    return {"success": True, "data": {"id": req.id, "status": "REJECTED"}}


# ─── Tickets ──────────────────────────────────────────────────────────────────

def create_ticket(
    db: Session, user: Employee,
    title: str, description: str = "",
    category: str = "OTHER", priority: str = "MEDIUM",
) -> dict:
    try:
        cat = TicketCategory[category.upper()]
        pri = TicketPriority[priority.upper()]
    except KeyError as e:
        return {"success": False, "error": f"Invalid value: {e}"}

    ticket = Ticket(
        title=title,
        description=description,
        category=cat,
        priority=pri,
        status=TicketStatus.OPEN,
        created_by_id=user.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"success": True, "data": {"id": ticket.id, "title": title, "status": "OPEN"}}


def assign_ticket(
    db: Session, actor: Employee,
    ticket_id: int, assignee_id: int,
    status: Optional[str] = None,
) -> dict:
    if actor.role == EmployeeRole.EMPLOYEE:
        return {"success": False, "error": "You do not have permission to assign tickets."}
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return {"success": False, "error": f"Ticket #{ticket_id} not found."}
    ticket.assigned_to_id = assignee_id
    if status:
        try:
            ticket.status = TicketStatus[status.upper()]
        except KeyError:
            pass
    db.commit()
    return {"success": True, "data": {"id": ticket_id, "assigned_to_id": assignee_id}}


# ─── Announcements ────────────────────────────────────────────────────────────

def create_announcement(
    db: Session, actor: Employee,
    title: str, content: str,
    category: str = "GENERAL", is_pinned: bool = False,
) -> dict:
    if actor.role == EmployeeRole.EMPLOYEE:
        return {"success": False, "error": "You do not have permission to create announcements."}
    try:
        cat = AnnouncementCategory[category.upper()]
    except KeyError:
        cat = AnnouncementCategory.GENERAL

    ann = Announcement(
        title=title, content=content,
        category=cat, is_pinned=is_pinned,
        created_by_id=actor.id,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return {"success": True, "data": {"id": ann.id, "title": title}}


# ─── Projects ────────────────────────────────────────────────────────────────

def assign_employee_to_project(
    db: Session, actor: Employee,
    employee_id: int, project_id: int, role: str = "Member",
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
    return {"success": True, "data": {"employee_id": employee_id, "project_id": project_id, "role": role}}
