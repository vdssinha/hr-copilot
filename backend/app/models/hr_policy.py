import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class PolicyCategory(str, enum.Enum):
    LEAVE = "LEAVE"
    ATTENDANCE = "ATTENDANCE"
    CODE_OF_CONDUCT = "CODE_OF_CONDUCT"
    BENEFITS = "BENEFITS"
    COMPENSATION = "COMPENSATION"
    IT = "IT"
    GENERAL = "GENERAL"


class HRPolicy(Base):
    __tablename__ = "hr_policies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(SAEnum(PolicyCategory), nullable=False, default=PolicyCategory.GENERAL)
    filename = Column(String(300), nullable=True)
    is_active = Column(Boolean, default=True)
    created_by_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    embeddings_generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = relationship("Employee", foreign_keys=[created_by_id])
