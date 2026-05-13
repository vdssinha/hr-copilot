"""Admin-only endpoints: user CRUD, role access management, category management, policy upload."""
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import POLICY_UPLOAD_DIR
from app.core.dependencies import get_current_user, require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.ai_audit_log import AIAuditLog, AIIntent, ActionStatus
from app.models.announcement import Announcement
from app.models.employee import Employee, EmployeeRole, EmploymentType, EmployeeStatus
from app.models.job_history import JobHistory
from app.models.leave import LeaveBalance, LeaveRequest
from app.models.onboarding import OnboardingTask
from app.models.payroll import PayrollRecord
from app.models.project import EmployeeProject
from app.models.skill import EmployeeSkill
from app.models.ticket import Ticket
from app.models.hr_policy import HRPolicy, PolicyCategory
from app.models.role_category_access import RoleCategoryAccess
from app.models.policy_group import PolicyGroup, GroupCategoryAccess
from app.schemas.admin import (
    AdminCategoryOut,
    AdminCategoryUpdate,
    AdminPolicyOut,
    AdminPolicyGroupCreate,
    AdminPolicyGroupOut,
    AdminPolicyGroupUpdate,
    AdminRoleOut,
    AdminRoleUpdate,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
)
from app.schemas.common import APIResponse
from app.services.ai.core.tools.document_loader import extract_text_bytes
from sqlalchemy import func, case, or_
from app.services.ai.agents.hr_data_rag import ingest_hr_data
from app.services.ai.agents.policy_rag import ingest_policies

router = APIRouter()

_require_admin = require_role(EmployeeRole.ADMIN)

_ALLOWED_POLICY_EXTENSIONS = {".md", ".txt", ".pdf", ".docx"}


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[AdminUserOut])
def list_users(
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Employee).order_by(Employee.name).all()


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    current_user: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if db.query(Employee).filter(Employee.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.query(Employee).filter(Employee.employee_code == payload.employee_code).first():
        raise HTTPException(status_code=409, detail="Employee code already in use")

    employee = Employee(
        employee_code=payload.employee_code,
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        job_title=payload.job_title,
        department_id=payload.department_id,
        employment_type=payload.employment_type,
        status=EmployeeStatus.ACTIVE,
        joining_date=payload.joining_date,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    current_user: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    employee = db.query(Employee).filter(Employee.id == user_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="User not found")
    if employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot edit your own account via admin panel")

    if payload.email is not None:
        conflict = db.query(Employee).filter(
            Employee.email == payload.email, Employee.id != user_id
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Email already in use")
        employee.email = payload.email

    if payload.name is not None:
        employee.name = payload.name
    if payload.role is not None:
        employee.role = payload.role
    if payload.job_title is not None:
        employee.job_title = payload.job_title
    if payload.department_id is not None:
        employee.department_id = payload.department_id
    if payload.status is not None:
        employee.status = payload.status
    if "policy_group" in payload.model_fields_set:
        if payload.policy_group is not None:
            group = db.query(PolicyGroup).filter(PolicyGroup.name == payload.policy_group).first()
            if not group:
                raise HTTPException(status_code=400, detail=f"Policy group '{payload.policy_group}' not found")
        employee.policy_group = payload.policy_group

    db.commit()
    db.refresh(employee)
    return employee


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    employee = db.query(Employee).filter(Employee.id == user_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="User not found")
    if employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    eid = employee.id
    db.query(AIAuditLog).filter(AIAuditLog.user_id == eid).delete()
    db.query(LeaveRequest).filter(LeaveRequest.employee_id == eid).delete()
    db.query(LeaveBalance).filter(LeaveBalance.employee_id == eid).delete()
    db.query(EmployeeProject).filter(EmployeeProject.employee_id == eid).delete()
    db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == eid).delete()
    db.query(JobHistory).filter(JobHistory.employee_id == eid).delete()
    db.query(OnboardingTask).filter(OnboardingTask.employee_id == eid).delete()
    db.query(PayrollRecord).filter(PayrollRecord.employee_id == eid).delete()
    db.query(Announcement).filter(Announcement.created_by_id == eid).delete()
    db.query(Ticket).filter(Ticket.created_by_id == eid).delete()
    db.query(Ticket).filter(Ticket.assigned_to_id == eid).update({"assigned_to_id": None})
    db.query(Employee).filter(Employee.manager_id == eid).update({"manager_id": None})
    db.delete(employee)
    db.commit()


# ── Roles ─────────────────────────────────────────────────────────────────────

@router.get("/roles", response_model=List[AdminRoleOut])
def list_roles(
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(RoleCategoryAccess).all()
    role_map: dict = {r.value: [] for r in EmployeeRole}
    for row in rows:
        if row.role in role_map:
            role_map[row.role].append(row.category)
    return [AdminRoleOut(name=role, accessible_categories=cats) for role, cats in role_map.items()]


@router.patch("/roles/{role_name}", response_model=AdminRoleOut)
def update_role(
    role_name: str,
    payload: AdminRoleUpdate,
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        role = EmployeeRole(role_name.upper())
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")

    valid_cats = {c.value for c in PolicyCategory}
    invalid = [c for c in payload.accessible_categories if c not in valid_cats]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown categories: {invalid}")

    db.query(RoleCategoryAccess).filter(RoleCategoryAccess.role == role.value).delete()
    for cat in payload.accessible_categories:
        db.add(RoleCategoryAccess(role=role.value, category=cat))
    db.commit()

    return AdminRoleOut(name=role.value, accessible_categories=payload.accessible_categories)


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=List[AdminCategoryOut])
def list_categories(
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(RoleCategoryAccess).all()
    cat_map: dict = {c.value: [] for c in PolicyCategory}
    for row in rows:
        if row.category in cat_map:
            cat_map[row.category].append(row.role)
    return [AdminCategoryOut(name=cat, accessible_by_roles=roles) for cat, roles in cat_map.items()]


@router.patch("/categories/{category_name}", response_model=AdminCategoryOut)
def update_category(
    category_name: str,
    payload: AdminCategoryUpdate,
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        category = PolicyCategory(category_name.upper())
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Category '{category_name}' not found")

    valid_roles = {r.value for r in EmployeeRole}
    invalid = [r for r in payload.accessible_by_roles if r not in valid_roles]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown roles: {invalid}")

    db.query(RoleCategoryAccess).filter(RoleCategoryAccess.category == category.value).delete()
    for role in payload.accessible_by_roles:
        db.add(RoleCategoryAccess(role=role, category=category.value))
    db.commit()

    return AdminCategoryOut(name=category.value, accessible_by_roles=payload.accessible_by_roles)


# ── Policies ──────────────────────────────────────────────────────────────────

@router.get("/policies", response_model=List[AdminPolicyOut])
def list_policies(
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    return db.query(HRPolicy).order_by(HRPolicy.created_at.desc()).all()


@router.post("/policies/upload", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def upload_policy(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    current_user: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        policy_category = PolicyCategory(category.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category '{category}'")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_POLICY_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(_ALLOWED_POLICY_EXTENSIONS)}",
        )

    content = await file.read()
    try:
        text = extract_text_bytes(content, suffix, file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    upload_dir = Path(POLICY_UPLOAD_DIR) / policy_category.value.lower()
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / (file.filename or "upload")
    file_path.write_bytes(content)

    policy = HRPolicy(
        title=title,
        content=text,
        category=policy_category,
        filename=file.filename,
        is_active=True,
        created_by_id=current_user.id,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)

    background_tasks.add_task(ingest_policies, db)

    return APIResponse.ok({"policy_id": policy.id, "status": "ingestion_queued"})


@router.post("/hr-data/ingest", response_model=APIResponse)
def ingest_hr_data_endpoint(
    background_tasks: BackgroundTasks,
    _: Employee = Depends(_require_admin),
):
    """Re-ingest hr_data.csv into the hr_data vector store collection."""
    csv_path = Path(POLICY_UPLOAD_DIR).parent / "employees" / "hr_data.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="hr_data.csv not found")
    background_tasks.add_task(ingest_hr_data, csv_path)
    return APIResponse.ok({"status": "ingestion_queued", "file": str(csv_path)})


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: int,
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    policy = db.query(HRPolicy).filter(HRPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    from app.services.ai import factory as _factory
    store = _factory.get_vector_store("hr_policies")
    try:
        store.delete_where({"policy_id": policy_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VectorDB purge failed: {e}")

    db.delete(policy)
    db.commit()


# ── Policy Groups ─────────────────────────────────────────────────────────────

def _group_to_out(db: Session, group: PolicyGroup) -> AdminPolicyGroupOut:
    cats = [r.category for r in db.query(GroupCategoryAccess).filter(GroupCategoryAccess.group_name == group.name).all()]
    return AdminPolicyGroupOut(name=group.name, accessible_categories=sorted(cats))


@router.get("/policy-groups", response_model=List[AdminPolicyGroupOut])
def list_policy_groups(
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    groups = db.query(PolicyGroup).order_by(PolicyGroup.name).all()
    return [_group_to_out(db, g) for g in groups]


@router.post("/policy-groups", response_model=AdminPolicyGroupOut, status_code=status.HTTP_201_CREATED)
def create_policy_group(
    payload: AdminPolicyGroupCreate,
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    name = payload.name.strip().lower().replace(" ", "_")
    if db.query(PolicyGroup).filter(PolicyGroup.name == name).first():
        raise HTTPException(status_code=409, detail=f"Policy group '{name}' already exists")

    valid_cats = {c.value for c in PolicyCategory}
    invalid = [c for c in payload.accessible_categories if c not in valid_cats]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown categories: {invalid}")

    group = PolicyGroup(name=name)
    db.add(group)
    for cat in payload.accessible_categories:
        db.add(GroupCategoryAccess(group_name=name, category=cat))
    db.commit()
    db.refresh(group)
    return _group_to_out(db, group)


@router.patch("/policy-groups/{group_name}", response_model=AdminPolicyGroupOut)
def update_policy_group(
    group_name: str,
    payload: AdminPolicyGroupUpdate,
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    group = db.query(PolicyGroup).filter(PolicyGroup.name == group_name).first()
    if not group:
        raise HTTPException(status_code=404, detail=f"Policy group '{group_name}' not found")

    valid_cats = {c.value for c in PolicyCategory}
    invalid = [c for c in payload.accessible_categories if c not in valid_cats]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown categories: {invalid}")

    db.query(GroupCategoryAccess).filter(GroupCategoryAccess.group_name == group_name).delete()
    for cat in payload.accessible_categories:
        db.add(GroupCategoryAccess(group_name=group_name, category=cat))
    db.commit()
    return _group_to_out(db, group)


@router.delete("/policy-groups/{group_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy_group(
    group_name: str,
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    group = db.query(PolicyGroup).filter(PolicyGroup.name == group_name).first()
    if not group:
        raise HTTPException(status_code=404, detail=f"Policy group '{group_name}' not found")
    db.query(GroupCategoryAccess).filter(GroupCategoryAccess.group_name == group_name).delete()
    db.query(Employee).filter(Employee.policy_group == group_name).update({"policy_group": None})
    db.delete(group)
    db.commit()


# ── AI Usage Dashboard ────────────────────────────────────────────────────────

@router.get("/ai-stats", response_model=APIResponse)
def ai_usage_stats(
    days: int = 30,
    _: Employee = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> APIResponse:
    since = datetime.utcnow() - timedelta(days=days)
    base = db.query(AIAuditLog).filter(AIAuditLog.created_at >= since)

    total = base.count()

    # by intent
    by_intent = [
        {"intent": row[0].value if row[0] else "UNKNOWN", "count": row[1]}
        for row in db.query(AIAuditLog.intent, func.count(AIAuditLog.id))
                     .filter(AIAuditLog.created_at >= since)
                     .group_by(AIAuditLog.intent)
                     .order_by(func.count(AIAuditLog.id).desc())
                     .all()
    ]

    # by tool — exclude null tool_name (error entries without a tool) but show them as "error"
    by_tool = [
        {"tool": row[0] if row[0] else "error", "count": row[1]}
        for row in db.query(AIAuditLog.tool_name, func.count(AIAuditLog.id))
                     .filter(AIAuditLog.created_at >= since)
                     .group_by(AIAuditLog.tool_name)
                     .order_by(func.count(AIAuditLog.id).desc())
                     .all()
    ]

    # failed permission attempts: HR_ACTION refused (permission denied) + UNKNOWN refused (guardrail blocks)
    # Excludes RAG no-answer (policy_rag/hr_data_rag REFUSED = no content found, not a permission failure)
    permission_failures = base.filter(
        AIAuditLog.action_status == ActionStatus.REFUSED,
        or_(
            AIAuditLog.intent == AIIntent.HR_ACTION,
            AIAuditLog.intent == AIIntent.UNKNOWN,
        ),
    ).count()

    # error count: interactions that threw exceptions
    error_count = base.filter(AIAuditLog.action_status == ActionStatus.ERROR).count()

    # avg latency (exclude NULLs)
    avg_lat = db.query(func.avg(AIAuditLog.latency_ms))\
                .filter(AIAuditLog.created_at >= since, AIAuditLog.latency_ms.isnot(None))\
                .scalar()

    # RAG no-answer rate: policy_rag + hr_data_rag calls where status=REFUSED / total RAG calls
    rag_tools = ["policy_rag", "hr_data_rag"]
    rag_total = base.filter(AIAuditLog.tool_name.in_(rag_tools)).count()
    rag_no_answer = base.filter(
        AIAuditLog.tool_name.in_(rag_tools),
        AIAuditLog.action_status == ActionStatus.REFUSED,
    ).count()
    rag_no_answer_rate = round(rag_no_answer / rag_total * 100, 1) if rag_total else 0.0

    # SQL blocked count: sql_agent REFUSED = security guardrail blocked the query
    sql_blocked = base.filter(
        AIAuditLog.tool_name == "sql_agent",
        AIAuditLog.action_status == ActionStatus.REFUSED,
    ).count()

    # success count
    success_count = base.filter(AIAuditLog.action_status == ActionStatus.SUCCESS).count()

    # requests per day (last 14 days — fixed window for chart)
    daily = []
    for i in range(13, -1, -1):
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = db.query(AIAuditLog)\
                  .filter(AIAuditLog.created_at >= day_start, AIAuditLog.created_at < day_end)\
                  .count()
        daily.append({"date": day_start.strftime("%Y-%m-%d"), "count": count})

    return APIResponse.ok({
        "period_days": days,
        "total_requests": total,
        "success_count": success_count,
        "permission_failures": permission_failures,
        "error_count": error_count,
        "avg_latency_ms": round(avg_lat, 1) if avg_lat else None,
        "rag_no_answer_rate_pct": rag_no_answer_rate,
        "sql_blocked_count": sql_blocked,
        "by_intent": by_intent,
        "by_tool": by_tool,
        "daily": daily,
    })
