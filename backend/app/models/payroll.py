import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Date, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"


class PayrollRecord(Base):
    __tablename__ = "payroll_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    basic_salary_usd = Column(Float, nullable=False)
    allowances_usd = Column(Float, default=0.0)
    deductions_usd = Column(Float, default=0.0)
    net_salary_usd = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=True)
    payment_status = Column(SAEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="payroll_records")
