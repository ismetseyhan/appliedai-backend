"""rename templates and document_templates tables

Revision ID: 8e80760b9e7f
Revises: 64ec28fa0842
Create Date: 2025-12-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e80760b9e7f'
down_revision: Union[str, None] = '64ec28fa0842'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename templates table to parsing_templates
    op.rename_table('templates', 'parsing_templates')

    # 2. Rename document_templates table to document_chunking
    op.rename_table('document_templates', 'document_chunking')

    # 3. Update foreign key constraint names in document_chunking
    # Drop old foreign key
    op.drop_constraint('document_templates_template_id_fkey', 'document_chunking', type_='foreignkey')
    # Create new foreign key with updated table name
    op.create_foreign_key(
        'document_chunking_parsing_template_id_fkey',
        'document_chunking', 'parsing_templates',
        ['template_id'], ['id'],
        ondelete='CASCADE'
    )

    # 4. Update foreign key constraint names in document_chunks
    # Drop old foreign key
    op.drop_constraint('fk_document_chunks_document_template_id', 'document_chunks', type_='foreignkey')
    # Create new foreign key with updated table name
    op.create_foreign_key(
        'fk_document_chunks_document_chunking_id',
        'document_chunks', 'document_chunking',
        ['document_template_id'], ['id'],
        ondelete='CASCADE'
    )

    # 5. Rename column in document_chunks for clarity
    op.alter_column('document_chunks', 'document_template_id', new_column_name='document_chunking_id')


def downgrade() -> None:
    # Reverse order of upgrade

    # 5. Rename column back
    op.alter_column('document_chunks', 'document_chunking_id', new_column_name='document_template_id')

    # 4. Restore old foreign key in document_chunks
    op.drop_constraint('fk_document_chunks_document_chunking_id', 'document_chunks', type_='foreignkey')
    op.create_foreign_key(
        'fk_document_chunks_document_template_id',
        'document_chunks', 'document_templates',
        ['document_template_id'], ['id'],
        ondelete='CASCADE'
    )

    # 3. Restore old foreign key in document_templates
    op.drop_constraint('document_chunking_parsing_template_id_fkey', 'document_chunking', type_='foreignkey')
    op.create_foreign_key(
        'document_templates_template_id_fkey',
        'document_templates', 'templates',
        ['template_id'], ['id'],
        ondelete='CASCADE'
    )

    # 2. Rename document_chunking back to document_templates
    op.rename_table('document_chunking', 'document_templates')

    # 1. Rename parsing_templates back to templates
    op.rename_table('parsing_templates', 'templates')
