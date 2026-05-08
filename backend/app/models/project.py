import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Date, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class ProjectStatus(str, enum.Enum):
    PLANNING = "PLANNING"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    ON_HOLD = "ON_HOLD"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(300), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(ProjectStatus), nullable=False, default=ProjectStatus.PLANNING)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee_projects = relationship("EmployeeProject", back_populates="project")


class EmployeeProject(Base):
    __tablename__ = "employee_projects"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    role = Column(String(200), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    employee = relationship("Employee", back_populates="employee_projects")
    project = relationship("Project", back_populates="employee_projects")
