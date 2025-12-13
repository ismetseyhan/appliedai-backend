"""add rag fields to templates

Revision ID: 6890697cad1b
Revises: 207a977bc32b
Create Date: 2025-12-13 00:52:21.317959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6890697cad1b'
down_revision: Union[str, Sequence[str], None] = '207a977bc32b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('templates', sa.Column('parsed_record_preview', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('templates', sa.Column('metadata_keywords', postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column('templates', sa.Column('llm_text', postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column('templates', sa.Column('embedding_text', postgresql.ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column('templates', 'embedding_text')
    op.drop_column('templates', 'llm_text')
    op.drop_column('templates', 'metadata_keywords')
    op.drop_column('templates', 'parsed_record_preview')
