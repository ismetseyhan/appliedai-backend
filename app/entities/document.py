from sqlalchemy import Column, String, BigInteger, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
import enum


def generate_uuid():
    return str(uuid.uuid4())


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String, nullable=False, default='application/pdf')
    is_public = Column(Boolean, nullable=False, default=False, index=True)
    processing_status = Column(
        SQLEnum(ProcessingStatus),
        nullable=False,
        default=ProcessingStatus.PENDING,
        index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="documents")

    def __repr__(self):
        return f"<Document {self.file_name} by {self.user_id}>"
