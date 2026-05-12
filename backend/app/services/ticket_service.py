"""
Ticket business logic — single source of truth for all ticket operations.
Called by both api_tools.py (AI agent path) and REST endpoints.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee, EmployeeRole
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus


def create_ticket(
    db: Session,
    user: Employee,
    title: str,
    description: str = "",
    category: str = "OTHER",
    priority: str = "MEDIUM",
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
    db: Session,
    actor: Employee,
    ticket_id: int,
    assignee_id: int,
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


def list_all_tickets(db: Session, actor: Employee, limit: int = 50) -> dict:
    """MANAGER/HR/ADMIN/C_LEVEL: all tickets. EMPLOYEE: own only."""
    privileged = {EmployeeRole.MANAGER, EmployeeRole.HR, EmployeeRole.ADMIN, EmployeeRole.C_LEVEL}
    if actor.role not in privileged:
        return check_ticket_status(db=db, user=actor, limit=limit)

    tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(limit).all()
    data = [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status.value,
            "priority": t.priority.value,
            "category": t.category.value,
            "created_by_id": t.created_by_id,
            "assigned_to_id": t.assigned_to_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tickets
    ]
    return {"success": True, "data": data}


def check_ticket_status(db: Session, user: Employee, limit: int = 20) -> dict:
    """Returns own tickets ordered by created_at DESC."""
    tickets = (
        db.query(Ticket)
        .filter(Ticket.created_by_id == user.id)
        .order_by(Ticket.created_at.desc())
        .limit(limit)
        .all()
    )
    data = [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status.value,
            "priority": t.priority.value,
            "category": t.category.value,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tickets
    ]
    return {"success": True, "data": data}
