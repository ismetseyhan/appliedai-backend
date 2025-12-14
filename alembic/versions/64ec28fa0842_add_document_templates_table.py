"""add_document_templates_table

Revision ID: 64ec28fa0842
Revises: a7d79f38f3a2
Create Date: 2025-12-13 21:41:20.887842

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '64ec28fa0842'
down_revision: Union[str, Sequence[str], None] = 'a7d79f38f3a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create document_templates table
    op.create_table(
        'document_templates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('agent_prompt', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'document_id', name='uq_user_document')
    )

    # Create indexes for document_templates
    op.create_index('idx_document_templates_user_id', 'document_templates', ['user_id'])
    op.create_index('idx_document_templates_document_id', 'document_templates', ['document_id'])
    op.create_index('idx_document_templates_template_id', 'document_templates', ['template_id'])
    op.create_index('idx_document_templates_is_public', 'document_templates', ['is_public'])

    # 2. Add document_template_id column to document_chunks (nullable for migration)
    op.add_column('document_chunks', sa.Column('document_template_id', sa.String(), nullable=True))

    # 3. Migrate existing data (if any chunks exist)
    # Get connection for data migration
    conn = op.get_bind()

    # Find all unique (user_id, document_id, template_id) combinations
    result = conn.execute(sa.text("""
        SELECT DISTINCT
            d.user_id,
            dc.document_id,
            dc.template_id,
            d.file_name as document_name,
            t.template_name
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        LEFT JOIN templates t ON dc.template_id = t.id
    """))

    # For each unique combination, create a document_template and update chunks
    for row in result:
        # Generate UUID for document_template
        import uuid
        doc_template_id = str(uuid.uuid4())

        # Create document_template record
        conn.execute(sa.text("""
            INSERT INTO document_templates (id, user_id, document_id, template_id, name, description, is_public)
            VALUES (:id, :user_id, :document_id, :template_id, :name, :description, false)
        """), {
            'id': doc_template_id,
            'user_id': row.user_id,
            'document_id': row.document_id,
            'template_id': row.template_id,
            'name': f"Migrated: {row.document_name}",
            'description': f"Auto-migrated from legacy chunks (Template: {row.template_name or 'Unknown'})"
        })

        # Update chunks to reference new document_template
        conn.execute(sa.text("""
            UPDATE document_chunks
            SET document_template_id = :doc_template_id
            WHERE document_id = :document_id AND template_id = :template_id
        """), {
            'doc_template_id': doc_template_id,
            'document_id': row.document_id,
            'template_id': row.template_id
        })

    # 4. Add foreign key constraint for document_template_id
    op.create_foreign_key(
        'fk_document_chunks_document_template_id',
        'document_chunks',
        'document_templates',
        ['document_template_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # 5. Make document_template_id NOT NULL
    op.alter_column('document_chunks', 'document_template_id', nullable=False)

    # 6. Create index for document_template_id
    op.create_index('idx_document_chunks_document_template_id', 'document_chunks', ['document_template_id'])

    # 7. Drop old unique constraint
    op.drop_constraint('uq_doc_record_index', 'document_chunks', type_='unique')

    # 8. Drop old columns
    op.drop_constraint('document_records_document_id_fkey', 'document_chunks', type_='foreignkey')
    op.drop_constraint('document_records_template_id_fkey', 'document_chunks', type_='foreignkey')
    op.drop_index('ix_document_chunks_document_id', table_name='document_chunks', if_exists=True)
    op.drop_index('ix_document_chunks_template_id', table_name='document_chunks', if_exists=True)
    op.drop_column('document_chunks', 'document_id')
    op.drop_column('document_chunks', 'template_id')

    # 9. Add new unique constraint
    op.create_unique_constraint('uq_doctemplate_chunk_index', 'document_chunks', ['document_template_id', 'record_index'])


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop new unique constraint
    op.drop_constraint('uq_doctemplate_chunk_index', 'document_chunks', type_='unique')

    # 2. Re-add old columns to document_chunks
    op.add_column('document_chunks', sa.Column('template_id', sa.String(), nullable=True))
    op.add_column('document_chunks', sa.Column('document_id', sa.String(), nullable=True))

    # 3. Copy data back from document_templates
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE document_chunks dc
        SET document_id = dt.document_id,
            template_id = dt.template_id
        FROM document_templates dt
        WHERE dc.document_template_id = dt.id
    """))

    # 4. Make old columns NOT NULL and add foreign keys
    op.alter_column('document_chunks', 'document_id', nullable=False)
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('ix_document_chunks_template_id', 'document_chunks', ['template_id'])
    op.create_foreign_key('document_records_document_id_fkey', 'document_chunks', 'documents', ['document_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('document_records_template_id_fkey', 'document_chunks', 'templates', ['template_id'], ['id'], ondelete='SET NULL')

    # 5. Re-add old unique constraint
    op.create_unique_constraint('uq_doc_record_index', 'document_chunks', ['document_id', 'record_index'])

    # 6. Drop new column and constraint
    op.drop_index('idx_document_chunks_document_template_id', table_name='document_chunks')
    op.drop_constraint('fk_document_chunks_document_template_id', 'document_chunks', type_='foreignkey')
    op.drop_column('document_chunks', 'document_template_id')

    # 7. Drop document_templates table (cascades handled by ondelete)
    op.drop_index('idx_document_templates_is_public', table_name='document_templates')
    op.drop_index('idx_document_templates_template_id', table_name='document_templates')
    op.drop_index('idx_document_templates_document_id', table_name='document_templates')
    op.drop_index('idx_document_templates_user_id', table_name='document_templates')
    op.drop_table('document_templates')
