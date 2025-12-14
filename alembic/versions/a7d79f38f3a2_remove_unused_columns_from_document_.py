"""remove unused columns from document_chunks

Revision ID: a7d79f38f3a2
Revises: 885fbb8c99fb
Create Date: 2025-12-13 19:16:45.659282

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a7d79f38f3a2'
down_revision: Union[str, Sequence[str], None] = '885fbb8c99fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index('ix_document_chunks_record_id', table_name='document_chunks', if_exists=True)
    op.drop_column('document_chunks', 'record_id', if_exists=True)
    op.drop_column('document_chunks', 'record_type', if_exists=True)
    op.drop_column('document_chunks', 'raw_record_text', if_exists=True)
    op.drop_column('document_chunks', 'parsing_metadata', if_exists=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('document_chunks', sa.Column('parsing_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('document_chunks', sa.Column('raw_record_text', sa.Text(), nullable=True))
    op.add_column('document_chunks', sa.Column('record_type', sa.String(length=100), nullable=True))
    op.add_column('document_chunks', sa.Column('record_id', sa.String(), nullable=True))
    op.create_index('ix_document_chunks_record_id', 'document_chunks', ['record_id'])
