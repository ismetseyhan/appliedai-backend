"""refactor to document_chunks with pgvector

Revision ID: 885fbb8c99fb
Revises: 6890697cad1b
Create Date: 2025-12-13 18:47:50.459084

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '885fbb8c99fb'
down_revision: Union[str, Sequence[str], None] = '6890697cad1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # 2. Rename table: document_records → document_chunks
    op.rename_table('document_records', 'document_chunks')

    # 3. Rename column: fields → raw_object
    op.alter_column('document_chunks', 'fields', new_column_name='raw_object')

    # 4. Add new columns
    op.add_column('document_chunks', sa.Column('llm_text', sa.Text(), nullable=True))
    op.add_column('document_chunks', sa.Column('embedding_text', sa.Text(), nullable=True))
    op.add_column('document_chunks', sa.Column('embedding', Vector(1536), nullable=True))
    op.add_column('document_chunks', sa.Column('chunk_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Note: Skipping index creation - pgvector indexes support max 2000 dimensions
    # 3072-dim vectors will use sequential scan for similarity (slower but works)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop new columns
    op.drop_column('document_chunks', 'chunk_metadata')
    op.drop_column('document_chunks', 'embedding')
    op.drop_column('document_chunks', 'embedding_text')
    op.drop_column('document_chunks', 'llm_text')

    # Rename column back: raw_object → fields
    op.alter_column('document_chunks', 'raw_object', new_column_name='fields')

    # Rename table back: document_chunks → document_records
    op.rename_table('document_chunks', 'document_records')

    # Note: Not dropping pgvector extension in downgrade (may be used by other tables)
