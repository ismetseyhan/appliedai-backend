"""update_is_active_default_to_false

Revision ID: 34b5c30baaab
Revises: 8e80760b9e7f
Create Date: 2025-12-14 17:57:16.637812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34b5c30baaab'
down_revision: Union[str, Sequence[str], None] = '8e80760b9e7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Change is_active default to false and update existing records."""
    # Change default value to false
    op.alter_column(
        'document_chunking',
        'is_active',
        server_default=sa.text('false'),
        existing_nullable=True
    )

    # Update existing records without prompt to false
    op.execute("""
        UPDATE document_chunking
        SET is_active = false
        WHERE agent_prompt IS NULL OR agent_prompt = ''
    """)


def downgrade() -> None:
    """Downgrade schema: Revert is_active default back to true."""
    # Revert default value to true
    op.alter_column(
        'document_chunking',
        'is_active',
        server_default=sa.text('true'),
        existing_nullable=True
    )
