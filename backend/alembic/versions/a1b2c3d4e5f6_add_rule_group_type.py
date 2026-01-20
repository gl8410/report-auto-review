"""add_rule_group_type

Revision ID: a1b2c3d4e5f6
Revises: 3bde872f9e1f
Create Date: 2026-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3bde872f9e1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rule_groups', sa.Column('type', sa.String(), nullable=True, server_default='private'))
    op.create_index(op.f('ix_rule_groups_type'), 'rule_groups', ['type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_rule_groups_type'), table_name='rule_groups')
    op.drop_column('rule_groups', 'type')