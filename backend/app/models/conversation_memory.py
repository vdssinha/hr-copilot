import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class MemoryTier(str, enum.Enum):
    USER_PROFILE = "user_profile"   # Tier 1: cross-session, cross-agent
    SESSION      = "session"        # Tier 2: within session, cross-agent (with provenance)
    AGENT        = "agent"          # Tier 3: within session, agent-local


class ConversationMemory(Base):
    __tablename__ = "conversation_memories"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    session_id   = Column(String(100), nullable=True, index=True)   # null for Tier 1
    agent_name   = Column(String(50),  nullable=True)               # null for Tier 1/2
    tier         = Column(SAEnum(MemoryTier), nullable=False, index=True)
    content      = Column(Text, nullable=False)
    source_agent = Column(String(50),  nullable=True)               # provenance for Tier 2
    created_at   = Column(DateTime, default=datetime.utcnow)
    expires_at   = Column(DateTime, nullable=True)

    user = relationship("Employee", foreign_keys=[user_id])
