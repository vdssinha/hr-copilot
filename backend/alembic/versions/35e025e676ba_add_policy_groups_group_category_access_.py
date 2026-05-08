"""add policy_groups group_category_access and employee policy_group

Revision ID: 35e025e676ba
Revises: 002
Create Date: 2026-05-08 22:33:25.487104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35e025e676ba'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = {r[0] for r in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}

    if 'policy_groups' not in existing:
        op.create_table(
            'policy_groups',
            sa.Column('name', sa.String(length=100), primary_key=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    if 'group_category_access' not in existing:
        op.create_table(
            'group_category_access',
            sa.Column('group_name', sa.String(length=100), primary_key=True, nullable=False),
            sa.Column('category', sa.String(length=50), primary_key=True, nullable=False),
            sa.UniqueConstraint('group_name', 'category', name='uq_group_category'),
        )

    cols = {r[1] for r in conn.execute(sa.text("PRAGMA table_info(employees)")).fetchall()}
    if 'policy_group' not in cols:
        op.add_column('employees', sa.Column('policy_group', sa.String(length=100), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    cols = {r[1] for r in conn.execute(sa.text("PRAGMA table_info(employees)")).fetchall()}
    if 'policy_group' in cols:
        op.drop_column('employees', 'policy_group')
    op.drop_table('group_category_access')
    op.drop_table('policy_groups')
