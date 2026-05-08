import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class OnboardingStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    task_name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(OnboardingStatus), nullable=False, default=OnboardingStatus.PENDING)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="onboarding_tasks")
