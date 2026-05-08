from sqlalchemy import Column, String, UniqueConstraint
from app.db.base import Base


class RoleCategoryAccess(Base):
    """Maps which PolicyCategory values each EmployeeRole can retrieve from the vector store."""

    __tablename__ = "role_category_access"

    role = Column(String(50), primary_key=True, nullable=False)
    category = Column(String(50), primary_key=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("role", "category", name="uq_role_category"),
    )
