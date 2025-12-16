"""create_sqlite_databases_table

Revision ID: 869418b7c6bd
Revises: fc8b1d320cb7
Create Date: 2025-12-08 17:30:12.113305

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = '869418b7c6bd'
down_revision: Union[str, Sequence[str], None] = 'fc8b1d320cb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'sqlite_databases',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('database_name', sa.String(), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('storage_path', sa.String(), nullable=False),
        sa.Column('allowed_operations', JSONB, nullable=False),
        sa.Column('sql_agent_prompt', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_path')
    )
    op.create_index(op.f('ix_sqlite_databases_storage_path'), 'sqlite_databases', ['storage_path'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_sqlite_databases_storage_path'), table_name='sqlite_databases')
    op.drop_table('sqlite_databases')
