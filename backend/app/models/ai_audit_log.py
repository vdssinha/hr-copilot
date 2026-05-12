import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class AIIntent(str, enum.Enum):
    POLICY_QA = "POLICY_QA"
    SQL_QUERY = "SQL_QUERY"
    HR_ACTION = "HR_ACTION"
    ROUTER = "ROUTER"
    UNKNOWN = "UNKNOWN"


class ActionStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    REFUSED = "REFUSED"
    ERROR = "ERROR"


class AIAuditLog(Base):
    __tablename__ = "ai_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    role = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    intent = Column(SAEnum(AIIntent), nullable=True)
    tool_name = Column(String(100), nullable=True)
    action_status = Column(SAEnum(ActionStatus), nullable=True)
    records_accessed = Column(Text, nullable=True)  # JSON string
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("Employee", back_populates="ai_audit_logs")
