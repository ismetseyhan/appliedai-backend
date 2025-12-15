"""create_conversations_tables

Revision ID: c8ff9524b7a4
Revises: 34b5c30baaab
Create Date: 2025-12-15 15:09:18.966683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8ff9524b7a4'
down_revision: Union[str, Sequence[str], None] = '34b5c30baaab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

    # Create indexes for conversations
    op.create_index('idx_conversations_user_id', 'conversations', ['user_id'])
    op.create_index('idx_conversations_created_at', 'conversations', ['created_at'])

    # Create conversation_messages table
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('agent_metadata', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE')
    )

    # Create indexes for conversation_messages
    op.create_index('idx_conversation_messages_conversation_id', 'conversation_messages', ['conversation_id'])
    op.create_index('idx_conversation_messages_created_at', 'conversation_messages', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop conversation_messages table and indexes
    op.drop_index('idx_conversation_messages_created_at', table_name='conversation_messages')
    op.drop_index('idx_conversation_messages_conversation_id', table_name='conversation_messages')
    op.drop_table('conversation_messages')

    # Drop conversations table and indexes
    op.drop_index('idx_conversations_created_at', table_name='conversations')
    op.drop_index('idx_conversations_user_id', table_name='conversations')
    op.drop_table('conversations')
