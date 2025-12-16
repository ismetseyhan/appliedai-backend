"""create_user_preferences_table

Revision ID: 4140d472bf11
Revises: 869418b7c6bd
Create Date: 2025-12-10 16:25:12.853591

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4140d472bf11'
down_revision: Union[str, Sequence[str], None] = '869418b7c6bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('preference_key', sa.String(), nullable=False),
        sa.Column('preference_value', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'preference_key', name='uq_user_preference')
    )
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'])
    op.create_index('ix_user_preferences_preference_key', 'user_preferences', ['preference_key'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_user_preferences_preference_key', 'user_preferences')
    op.drop_index('ix_user_preferences_user_id', 'user_preferences')
    op.drop_table('user_preferences')
