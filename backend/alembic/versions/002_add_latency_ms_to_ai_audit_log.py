"""add latency_ms to ai_audit_logs

Revision ID: 002
Revises: 001
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_audit_logs", sa.Column("latency_ms", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_audit_logs", "latency_ms")
