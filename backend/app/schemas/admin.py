from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel, EmailStr

from app.models.employee import EmployeeRole, EmploymentType, EmployeeStatus
from app.models.hr_policy import PolicyCategory


# ── Users ─────────────────────────────────────────────────────────────────────

class AdminUserOut(BaseModel):
    id: int
    employee_code: str
    name: str
    email: str
    role: EmployeeRole
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    employment_type: EmploymentType
    status: EmployeeStatus
    joining_date: Optional[date] = None

    model_config = {"from_attributes": True}


class AdminUserCreate(BaseModel):
    employee_code: str
    name: str
    email: str
    password: str
    role: EmployeeRole = EmployeeRole.EMPLOYEE
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    joining_date: Optional[date] = None


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[EmployeeRole] = None
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    status: Optional[EmployeeStatus] = None


# ── Roles ─────────────────────────────────────────────────────────────────────

class AdminRoleOut(BaseModel):
    name: str
    accessible_categories: List[str]


class AdminRoleUpdate(BaseModel):
    accessible_categories: List[str]


# ── Categories ────────────────────────────────────────────────────────────────

class AdminCategoryOut(BaseModel):
    name: str
    accessible_by_roles: List[str]


class AdminCategoryUpdate(BaseModel):
    accessible_by_roles: List[str]


# ── Policies ──────────────────────────────────────────────────────────────────

class AdminPolicyOut(BaseModel):
    id: int
    title: str
    category: PolicyCategory
    filename: Optional[str] = None
    is_active: bool
    embeddings_generated_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
