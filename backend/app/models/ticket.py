import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class TicketCategory(str, enum.Enum):
    IT = "IT"
    HR = "HR"
    FACILITIES = "FACILITIES"
    FINANCE = "FINANCE"
    OTHER = "OTHER"


class TicketPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(SAEnum(TicketCategory), nullable=False, default=TicketCategory.OTHER)
    priority = Column(SAEnum(TicketPriority), nullable=False, default=TicketPriority.MEDIUM)
    status = Column(SAEnum(TicketStatus), nullable=False, default=TicketStatus.OPEN)
    created_by_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = relationship("Employee", foreign_keys=[created_by_id], back_populates="tickets_created")
    assigned_to = relationship("Employee", foreign_keys=[assigned_to_id], back_populates="tickets_assigned")
