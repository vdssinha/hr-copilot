import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Date, Text, ForeignKey, Float, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class LeaveType(str, enum.Enum):
    CASUAL = "CASUAL"
    SICK = "SICK"
    ANNUAL = "ANNUAL"
    UNPAID = "UNPAID"


class HalfDayPeriod(str, enum.Enum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    year = Column(Integer, nullable=False)
    casual_leave_total = Column(Float, default=12.0)
    casual_leave_used = Column(Float, default=0.0)
    sick_leave_total = Column(Float, default=12.0)
    sick_leave_used = Column(Float, default=0.0)
    annual_leave_total = Column(Float, default=15.0)
    annual_leave_used = Column(Float, default=0.0)

    employee = relationship("Employee", back_populates="leave_balances")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    leave_type = Column(SAEnum(LeaveType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_half_day = Column(Boolean, default=False)
    half_day_period = Column(SAEnum(HalfDayPeriod), nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(SAEnum(LeaveStatus), nullable=False, default=LeaveStatus.PENDING)
    approved_by_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="leave_requests")
    approved_by = relationship("Employee", foreign_keys=[approved_by_id])
