from datetime import datetime
from sqlalchemy import Column, String, DateTime, UniqueConstraint
from app.db.base import Base


class PolicyGroup(Base):
    """Dynamic access group for policy RAG — admin-created, separate from EmployeeRole."""

    __tablename__ = "policy_groups"

    name = Column(String(100), primary_key=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class GroupCategoryAccess(Base):
    """Maps which PolicyCategory values each PolicyGroup can retrieve from the vector store."""

    __tablename__ = "group_category_access"

    group_name = Column(String(100), primary_key=True, nullable=False)
    category = Column(String(50), primary_key=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("group_name", "category", name="uq_group_category"),
    )
