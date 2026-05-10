"""add conversation_memories table for 3-tier memory system

Revision ID: 005
Revises: 004
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversation_memories",
        sa.Column("id",           sa.Integer(),     primary_key=True),
        sa.Column("user_id",      sa.Integer(),     sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("session_id",   sa.String(100),   nullable=True),
        sa.Column("agent_name",   sa.String(50),    nullable=True),
        sa.Column("tier",         sa.Enum("user_profile", "session", "agent", name="memorytier"), nullable=False),
        sa.Column("content",      sa.Text(),        nullable=False),
        sa.Column("source_agent", sa.String(50),    nullable=True),
        sa.Column("created_at",   sa.DateTime(),    nullable=True),
        sa.Column("expires_at",   sa.DateTime(),    nullable=True),
    )
    op.create_index("ix_conversation_memories_user_id",    "conversation_memories", ["user_id"])
    op.create_index("ix_conversation_memories_session_id", "conversation_memories", ["session_id"])
    op.create_index("ix_conversation_memories_tier",       "conversation_memories", ["tier"])


def downgrade():
    op.drop_index("ix_conversation_memories_tier",       "conversation_memories")
    op.drop_index("ix_conversation_memories_session_id", "conversation_memories")
    op.drop_index("ix_conversation_memories_user_id",    "conversation_memories")
    op.drop_table("conversation_memories")
    op.execute("DROP TYPE IF EXISTS memorytier")
