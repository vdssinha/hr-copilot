"""complete initial schema for greenfield setup

Revision ID: 001
Revises:
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

# All role/category access defaults consolidated from migrations 002 + 004
_ALL_CATS = ["LEAVE", "ATTENDANCE", "CODE_OF_CONDUCT", "BENEFITS", "COMPENSATION", "IT", "GENERAL"]

_ROLE_CATEGORY_DEFAULTS = (
    # EMPLOYEE — no compensation (salary is sensitive)
    [("EMPLOYEE", c) for c in _ALL_CATS if c != "COMPENSATION"]
    + [("MANAGER", c) for c in _ALL_CATS]
    + [("ADMIN",   c) for c in _ALL_CATS]
    + [("HR",      c) for c in _ALL_CATS]
    + [("C_LEVEL", c) for c in _ALL_CATS]
    + [("MARKETING", c) for c in _ALL_CATS if c != "COMPENSATION"]
)


def upgrade() -> None:
    bind = op.get_bind()

    # Create all ORM-mapped tables (including single-column indexes)
    from app.db.base import Base
    import app.models  # noqa — registers all models on Base.metadata
    Base.metadata.create_all(bind=bind)

    # Composite indexes on conversation_memories (not expressible in ORM without Index objects)
    op.create_index(
        "ix_conv_mem_user_session_tier",
        "conversation_memories",
        ["user_id", "session_id", "tier"],
    )
    op.create_index(
        "ix_conv_mem_user_session_agent",
        "conversation_memories",
        ["user_id", "session_id", "agent_name"],
    )

    # Seed role_category_access
    conn = op.get_bind()
    for role, cat in _ROLE_CATEGORY_DEFAULTS:
        conn.execute(
            sa.text("INSERT OR IGNORE INTO role_category_access (role, category) VALUES (:role, :cat)"),
            {"role": role, "cat": cat},
        )


def downgrade() -> None:
    bind = op.get_bind()
    from app.db.base import Base
    import app.models  # noqa
    Base.metadata.drop_all(bind=bind)
