"""add_comparison_document_ids

Revision ID: d5f8a9b3c1e2
Revises: cbce25388b3d
Create Date: 2025-12-25 11:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd5f8a9b3c1e2'
down_revision: Union[str, Sequence[str], None] = 'cbce25388b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add comparison_document_ids column to review_tasks table
    op.add_column('review_tasks', sa.Column('comparison_document_ids', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove comparison_document_ids column from review_tasks table
    op.drop_column('review_tasks', 'comparison_document_ids')
