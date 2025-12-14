from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class DocumentChunking(Base):
    __tablename__ = "document_chunking"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    document_id = Column(String, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    template_id = Column(String, ForeignKey('parsing_templates.id', ondelete='CASCADE'), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    agent_prompt = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=True, default=True)
    is_public = Column(Boolean, nullable=False, default=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    user = relationship("User", backref="document_chunking")
    document = relationship("Document")
    parsing_template = relationship("ParsingTemplate")
    chunks = relationship("DocumentChunk", back_populates="document_chunking", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('user_id', 'document_id', name='uq_user_document'),
    )

    def __repr__(self):
        return f"<DocumentChunking {self.name} (doc={self.document_id}, template={self.template_id})>"
