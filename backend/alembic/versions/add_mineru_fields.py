"""add mineru fields

Revision ID: add_mineru_fields
Revises: d5f8a9b3c1e2
Create Date: 2025-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_mineru_fields'
down_revision = 'd5f8a9b3c1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new fields to documents table
    op.add_column('documents', sa.Column('markdown_path', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('mineru_batch_id', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('mineru_zip_url', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('error_message', sa.String(), nullable=True))
    
    # Add new fields to comparison_documents table
    op.add_column('comparison_documents', sa.Column('markdown_path', sa.String(), nullable=True))
    op.add_column('comparison_documents', sa.Column('mineru_batch_id', sa.String(), nullable=True))
    op.add_column('comparison_documents', sa.Column('mineru_zip_url', sa.String(), nullable=True))
    op.add_column('comparison_documents', sa.Column('error_message', sa.String(), nullable=True))
    
    # Update status values - this is optional, existing data will keep old status values
    # New uploads will use new status values


def downgrade() -> None:
    # Remove fields from comparison_documents table
    op.drop_column('comparison_documents', 'error_message')
    op.drop_column('comparison_documents', 'mineru_zip_url')
    op.drop_column('comparison_documents', 'mineru_batch_id')
    op.drop_column('comparison_documents', 'markdown_path')
    
    # Remove fields from documents table
    op.drop_column('documents', 'error_message')
    op.drop_column('documents', 'mineru_zip_url')
    op.drop_column('documents', 'mineru_batch_id')
    op.drop_column('documents', 'markdown_path')

