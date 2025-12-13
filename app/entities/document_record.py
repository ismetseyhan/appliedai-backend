from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class DocumentRecord(Base):
    __tablename__ = "document_records"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    template_id = Column(String, ForeignKey('templates.id', ondelete='SET NULL'), index=True)
    record_index = Column(Integer, nullable=False)
    record_id = Column(String, index=True)
    record_type = Column(String(100))
    fields = Column(JSONB, nullable=False)
    raw_record_text = Column(Text)
    parsing_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", backref="records")
    template = relationship("Template")

    __table_args__ = (
        UniqueConstraint('document_id', 'record_index', name='uq_doc_record_index'),
    )

    def __repr__(self):
        return f"<DocumentRecord {self.record_id} from doc {self.document_id}>"
