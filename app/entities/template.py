from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class Template(Base):
    __tablename__ = "templates"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    template_name = Column(String(255), nullable=False)
    description = Column(Text)
    doc_type = Column(String(50), nullable=False, default='record_list')
    template_json = Column(JSONB, nullable=False)
    parsed_record_preview = Column(JSONB, nullable=True)
    metadata_keywords = Column(ARRAY(String), nullable=True)
    llm_text = Column(ARRAY(String), nullable=True)
    embedding_text = Column(ARRAY(String), nullable=True)
    is_public = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="templates")

    __table_args__ = (
        UniqueConstraint('user_id', 'template_name', name='uq_user_template_name'),
    )

    def __repr__(self):
        return f"<Template {self.template_name} by {self.user_id}>"
