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

# Sensible HR defaults:
#   EMPLOYEE  — no compensation (salary is sensitive)
#   MANAGER   — all categories
#   ADMIN     — all categories
_DEFAULTS = [
    ("EMPLOYEE", "LEAVE"),
    ("EMPLOYEE", "ATTENDANCE"),
    ("EMPLOYEE", "CODE_OF_CONDUCT"),
    ("EMPLOYEE", "BENEFITS"),
    ("EMPLOYEE", "IT"),
    ("EMPLOYEE", "GENERAL"),
    ("MANAGER", "LEAVE"),
    ("MANAGER", "ATTENDANCE"),
    ("MANAGER", "CODE_OF_CONDUCT"),
    ("MANAGER", "BENEFITS"),
    ("MANAGER", "COMPENSATION"),
    ("MANAGER", "IT"),
    ("MANAGER", "GENERAL"),
    ("ADMIN", "LEAVE"),
    ("ADMIN", "ATTENDANCE"),
    ("ADMIN", "CODE_OF_CONDUCT"),
    ("ADMIN", "BENEFITS"),
    ("ADMIN", "COMPENSATION"),
    ("ADMIN", "IT"),
    ("ADMIN", "GENERAL"),
]


def upgrade() -> None:
    conn = op.get_bind()
    existing_tables = {r[0] for r in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}

    if "role_category_access" not in existing_tables:
        op.create_table(
            "role_category_access",
            sa.Column("role", sa.String(50), primary_key=True, nullable=False),
            sa.Column("category", sa.String(50), primary_key=True, nullable=False),
            sa.UniqueConstraint("role", "category", name="uq_role_category"),
        )

    for role, cat in _DEFAULTS:
        conn.execute(
            sa.text("INSERT OR IGNORE INTO role_category_access (role, category) VALUES (:role, :cat)"),
            {"role": role, "cat": cat},
        )


def downgrade() -> None:
    op.drop_table("role_category_access")
