"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Import models so metadata is fully populated
    from app.db.base import Base
    import app.models  # noqa
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.db.base import Base
    import app.models  # noqa
    Base.metadata.drop_all(bind=bind)
