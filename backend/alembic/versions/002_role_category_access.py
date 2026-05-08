"""add role_category_access table

Revision ID: 002
Revises: 001
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

# All roles x all categories — fully open by default (preserves existing behaviour)
_ROLES = ["EMPLOYEE", "MANAGER", "ADMIN"]
_CATEGORIES = ["LEAVE", "ATTENDANCE", "CODE_OF_CONDUCT", "BENEFITS", "COMPENSATION", "IT", "GENERAL"]


def upgrade() -> None:
    op.create_table(
        "role_category_access",
        sa.Column("role", sa.String(50), primary_key=True, nullable=False),
        sa.Column("category", sa.String(50), primary_key=True, nullable=False),
        sa.UniqueConstraint("role", "category", name="uq_role_category"),
    )

    rca = sa.table(
        "role_category_access",
        sa.column("role", sa.String),
        sa.column("category", sa.String),
    )
    op.bulk_insert(rca, [
        {"role": role, "category": cat}
        for role in _ROLES
        for cat in _CATEGORIES
    ])


def downgrade() -> None:
    op.drop_table("role_category_access")
