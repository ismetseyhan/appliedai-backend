from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.core.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_chunking_id = Column(
        String,
        ForeignKey('document_chunking.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    record_index = Column(Integer, nullable=False)

    raw_object = Column(JSONB, nullable=False)
    llm_text = Column(Text, nullable=True)
    embedding_text = Column(Text, nullable=True)
    embedding = Column(Vector(1536), nullable=True)
    chunk_metadata = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document_chunking = relationship("DocumentChunking", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint('document_chunking_id', 'record_index', name='uq_doctemplate_chunk_index'),
    )

    def __repr__(self):
        return f"<DocumentChunk index={self.record_index} doc_chunking={self.document_chunking_id}>"
