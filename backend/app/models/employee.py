import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Date, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class EmployeeRole(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"
    HR = "HR"
    MARKETING = "MARKETING"
    C_LEVEL = "C_LEVEL"


class EmploymentType(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    NOTICE = "NOTICE"
    TERMINATED = "TERMINATED"


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(EmployeeRole), nullable=False, default=EmployeeRole.EMPLOYEE)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    job_title = Column(String(200), nullable=True)
    employment_type = Column(SAEnum(EmploymentType), nullable=False, default=EmploymentType.FULL_TIME)
    status = Column(SAEnum(EmployeeStatus), nullable=False, default=EmployeeStatus.ACTIVE)
    joining_date = Column(Date, nullable=True)
    # Sensitive fields — never exposed via SQL agent
    date_of_birth = Column(Date, nullable=True)
    current_salary_usd = Column(Float, nullable=True)
    bank_account_number = Column(String(50), nullable=True)
    bank_account_name = Column(String(200), nullable=True)
    bank_branch = Column(String(200), nullable=True)
    bank_ifsc = Column(String(20), nullable=True)
    pan_number = Column(String(20), nullable=True)
    pan_name = Column(String(200), nullable=True)
    pan_dob = Column(Date, nullable=True)
    profile_photo_path = Column(String(500), nullable=True)
    profile_photo_mime = Column(String(50), nullable=True)
    policy_group = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    department = relationship("Department", foreign_keys=[department_id], back_populates="employees")
    headed_department = relationship("Department", foreign_keys="Department.head_id", back_populates="head")
    manager = relationship("Employee", foreign_keys=[manager_id], back_populates="reports", remote_side="Employee.id")
    reports = relationship("Employee", foreign_keys=[manager_id], back_populates="manager")

    employee_projects = relationship("EmployeeProject", back_populates="employee")
    employee_skills = relationship("EmployeeSkill", back_populates="employee")
    job_history = relationship("JobHistory", back_populates="employee")
    leave_requests = relationship("LeaveRequest", foreign_keys="LeaveRequest.employee_id", back_populates="employee")
    leave_balances = relationship("LeaveBalance", back_populates="employee")
    tickets_created = relationship("Ticket", foreign_keys="Ticket.created_by_id", back_populates="created_by")
    tickets_assigned = relationship("Ticket", foreign_keys="Ticket.assigned_to_id", back_populates="assigned_to")
    announcements = relationship("Announcement", back_populates="created_by")
    onboarding_tasks = relationship("OnboardingTask", back_populates="employee")
    payroll_records = relationship("PayrollRecord", back_populates="employee")
    ai_audit_logs = relationship("AIAuditLog", back_populates="user")
