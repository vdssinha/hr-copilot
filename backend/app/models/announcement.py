import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class AnnouncementCategory(str, enum.Enum):
    GENERAL = "GENERAL"
    HR = "HR"
    IT = "IT"
    FACILITIES = "FACILITIES"
    CULTURE = "CULTURE"


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(SAEnum(AnnouncementCategory), nullable=False, default=AnnouncementCategory.GENERAL)
    is_pinned = Column(Boolean, default=False)
    created_by_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = relationship("Employee", back_populates="announcements")
