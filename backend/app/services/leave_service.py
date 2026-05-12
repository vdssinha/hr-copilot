"""
Leave business logic — single source of truth for all leave operations.
Called by both api_tools.py (AI agent path) and REST endpoints.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee, EmployeeRole
from app.models.leave import (
    LeaveRequest, LeaveType, LeaveStatus, LeaveBalance, HalfDayPeriod,
)


def apply_leave(
    db: Session,
    user: Employee,
    leave_type: str,
    start_date: str,
    end_date: str,
    reason: str = "",
    is_half_day: bool = False,
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
        return {
            "success": False,
            "error": f"Unknown leave type: {leave_type}. Use CASUAL, SICK, ANNUAL, or UNPAID.",
        }

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
            "message": "Leave request submitted. Status: Pending approval.",
        },
    }


def check_leave_balance(
    db: Session, user: Employee, year: Optional[int] = None
) -> dict:
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
            "casual": {
                "total": balance.casual_leave_total,
                "used": balance.casual_leave_used,
                "remaining": balance.casual_leave_total - balance.casual_leave_used,
            },
            "sick": {
                "total": balance.sick_leave_total,
                "used": balance.sick_leave_used,
                "remaining": balance.sick_leave_total - balance.sick_leave_used,
            },
            "annual": {
                "total": balance.annual_leave_total,
                "used": balance.annual_leave_used,
                "remaining": balance.annual_leave_total - balance.annual_leave_used,
            },
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


def list_pending_approvals(db: Session, actor: Employee) -> dict:
    """
    MANAGER: pending requests from direct reports only.
    HR / ADMIN / C_LEVEL: all pending requests.
    """
    query = db.query(LeaveRequest).filter(LeaveRequest.status == LeaveStatus.PENDING)

    if actor.role == EmployeeRole.MANAGER:
        # subquery: employees whose manager_id = actor.id
        from app.models.employee import Employee as Emp
        report_ids = [e.id for e in db.query(Emp).filter(Emp.manager_id == actor.id).all()]
        if not report_ids:
            return {"success": True, "data": []}
        query = query.filter(LeaveRequest.employee_id.in_(report_ids))
    elif actor.role == EmployeeRole.EMPLOYEE:
        return {"success": False, "error": "You do not have permission to view pending approvals."}

    requests = query.order_by(LeaveRequest.created_at.asc()).all()

    data = []
    for r in requests:
        data.append({
            "id": r.id,
            "employee_id": r.employee_id,
            "employee_name": r.employee.name if r.employee else None,
            "leave_type": r.leave_type.value,
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "reason": r.reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"success": True, "data": data}


def get_my_leaves(db: Session, user: Employee, limit: int = 20) -> dict:
    """Returns own leave requests ordered by created_at DESC."""
    requests = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.employee_id == user.id)
        .order_by(LeaveRequest.created_at.desc())
        .limit(limit)
        .all()
    )
    data = [
        {
            "id": r.id,
            "leave_type": r.leave_type.value,
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "status": r.status.value,
            "reason": r.reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in requests
    ]
    return {"success": True, "data": data}
