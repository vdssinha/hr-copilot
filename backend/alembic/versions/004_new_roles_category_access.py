"""add HR, MARKETING, C_LEVEL role category access

Revision ID: 004
Revises: 35e025e676ba
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "35e025e676ba"
branch_labels = None
depends_on = None

_ALL_CATS = ["LEAVE", "ATTENDANCE", "CODE_OF_CONDUCT", "BENEFITS", "COMPENSATION", "IT", "GENERAL"]

_NEW_DEFAULTS = (
    [("HR", cat) for cat in _ALL_CATS]
    + [("C_LEVEL", cat) for cat in _ALL_CATS]
    + [("MARKETING", cat) for cat in _ALL_CATS if cat != "COMPENSATION"]
)


def upgrade() -> None:
    conn = op.get_bind()
    for role, cat in _NEW_DEFAULTS:
        conn.execute(
            sa.text("INSERT OR IGNORE INTO role_category_access (role, category) VALUES (:role, :cat)"),
            {"role": role, "cat": cat},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for role in ("HR", "C_LEVEL", "MARKETING"):
        conn.execute(
            sa.text("DELETE FROM role_category_access WHERE role = :role"),
            {"role": role},
        )
