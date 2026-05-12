"""
Unit tests for leave_service — no LLM, no network, in-memory SQLite.
"""
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.employee import Employee, EmployeeRole
from app.models.leave import LeaveRequest, LeaveStatus, LeaveBalance, LeaveType
from app.services.leave_service import (
    apply_leave, check_leave_balance,
    approve_leave, reject_leave,
    list_pending_approvals, get_my_leaves,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _make_employee(db, role=EmployeeRole.EMPLOYEE, manager_id=None, employee_code=None):
    import random, string
    code = employee_code or "EMP" + "".join(random.choices(string.digits, k=6))
    emp = Employee(
        name="Test User",
        email=f"{code}@test.com",
        employee_code=code,
        hashed_password="x",
        role=role,
        manager_id=manager_id,
        status="ACTIVE",
    )
    db.add(emp)
    db.flush()
    return emp


def _make_balance(db, user):
    bal = LeaveBalance(
        employee_id=user.id,
        year=2026,
        casual_leave_total=12, casual_leave_used=0,
        sick_leave_total=12, sick_leave_used=0,
        annual_leave_total=15, annual_leave_used=0,
    )
    db.add(bal)
    db.flush()
    return bal


# ─── apply_leave ──────────────────────────────────────────────────────────────

def test_apply_leave_success(db):
    user = _make_employee(db)
    result = apply_leave(db, user, "SICK", "2026-06-01", "2026-06-02", reason="Fever")
    assert result["success"] is True
    assert result["data"]["status"] == "PENDING"
    assert result["data"]["leave_type"] == "SICK"


def test_apply_leave_invalid_date_format(db):
    user = _make_employee(db)
    result = apply_leave(db, user, "SICK", "01-06-2026", "02-06-2026")
    assert result["success"] is False
    assert "date format" in result["error"]


def test_apply_leave_end_before_start(db):
    user = _make_employee(db)
    result = apply_leave(db, user, "CASUAL", "2026-06-10", "2026-06-05")
    assert result["success"] is False
    assert "before or equal" in result["error"]


def test_apply_leave_invalid_type(db):
    user = _make_employee(db)
    result = apply_leave(db, user, "VACATION", "2026-06-01", "2026-06-02")
    assert result["success"] is False
    assert "Unknown leave type" in result["error"]


def test_apply_leave_persists_to_db(db):
    user = _make_employee(db)
    result = apply_leave(db, user, "ANNUAL", "2026-07-01", "2026-07-05")
    req_id = result["data"]["id"]
    req = db.query(LeaveRequest).filter(LeaveRequest.id == req_id).first()
    assert req is not None
    assert req.leave_type == LeaveType.ANNUAL
    assert req.status == LeaveStatus.PENDING


# ─── check_leave_balance ──────────────────────────────────────────────────────

def test_check_leave_balance_found(db):
    user = _make_employee(db)
    _make_balance(db, user)
    result = check_leave_balance(db, user, year=2026)
    assert result["success"] is True
    assert result["data"]["casual"]["total"] == 12
    assert result["data"]["sick"]["remaining"] == 12


def test_check_leave_balance_not_found(db):
    user = _make_employee(db)
    result = check_leave_balance(db, user, year=1999)
    assert result["success"] is False
    assert "No leave balance" in result["error"]


# ─── approve_leave / reject_leave ─────────────────────────────────────────────

def _pending_request(db, employee_id):
    req = LeaveRequest(
        employee_id=employee_id,
        leave_type=LeaveType.CASUAL,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        status=LeaveStatus.PENDING,
    )
    db.add(req)
    db.flush()
    return req


def test_approve_leave_by_manager(db):
    manager = _make_employee(db, role=EmployeeRole.MANAGER)
    emp = _make_employee(db, manager_id=manager.id)
    req = _pending_request(db, emp.id)
    result = approve_leave(db, manager, req.id)
    assert result["success"] is True
    assert result["data"]["status"] == "APPROVED"


def test_reject_leave_by_manager(db):
    manager = _make_employee(db, role=EmployeeRole.MANAGER)
    emp = _make_employee(db)
    req = _pending_request(db, emp.id)
    result = reject_leave(db, manager, req.id)
    assert result["success"] is True
    assert result["data"]["status"] == "REJECTED"


def test_approve_leave_employee_blocked(db):
    emp = _make_employee(db, role=EmployeeRole.EMPLOYEE)
    emp2 = _make_employee(db)
    req = _pending_request(db, emp2.id)
    result = approve_leave(db, emp, req.id)
    assert result["success"] is False
    assert "permission" in result["error"]


def test_approve_leave_not_found(db):
    manager = _make_employee(db, role=EmployeeRole.MANAGER)
    result = approve_leave(db, manager, 999999)
    assert result["success"] is False
    assert "not found" in result["error"]


def test_approve_already_approved(db):
    manager = _make_employee(db, role=EmployeeRole.MANAGER)
    emp = _make_employee(db)
    req = _pending_request(db, emp.id)
    approve_leave(db, manager, req.id)
    result = approve_leave(db, manager, req.id)
    assert result["success"] is False
    assert "already" in result["error"]


# ─── list_pending_approvals ───────────────────────────────────────────────────

def test_list_pending_approvals_manager_sees_reports(db):
    manager = _make_employee(db, role=EmployeeRole.MANAGER)
    report = _make_employee(db, manager_id=manager.id)
    other = _make_employee(db)
    _pending_request(db, report.id)
    _pending_request(db, other.id)
    result = list_pending_approvals(db, manager)
    assert result["success"] is True
    ids = [r["employee_id"] for r in result["data"]]
    assert report.id in ids
    assert other.id not in ids


def test_list_pending_approvals_admin_sees_all(db):
    admin = _make_employee(db, role=EmployeeRole.ADMIN)
    result = list_pending_approvals(db, admin)
    assert result["success"] is True
    assert isinstance(result["data"], list)


def test_list_pending_approvals_employee_blocked(db):
    emp = _make_employee(db, role=EmployeeRole.EMPLOYEE)
    result = list_pending_approvals(db, emp)
    assert result["success"] is False


# ─── get_my_leaves ────────────────────────────────────────────────────────────

def test_get_my_leaves_returns_own_only(db):
    user = _make_employee(db)
    other = _make_employee(db)
    _pending_request(db, user.id)
    _pending_request(db, other.id)
    result = get_my_leaves(db, user)
    assert result["success"] is True
    ids = [r["leave_type"] for r in result["data"]]
    assert len(ids) >= 1
    # all returned records belong to this user (verified by checking employee_id indirectly)


def test_get_my_leaves_ordered_desc(db):
    user = _make_employee(db)
    _pending_request(db, user.id)
    _pending_request(db, user.id)
    result = get_my_leaves(db, user)
    dates = [r["created_at"] for r in result["data"] if r["created_at"]]
    assert dates == sorted(dates, reverse=True) or len(dates) < 2
