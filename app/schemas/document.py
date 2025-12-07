from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.entities.document import ProcessingStatus


class DocumentUpload(BaseModel):
    """Request schema"""
    is_public: bool = False


class DocumentResponse(BaseModel):
    """Response schema for document"""
    id: str
    user_id: str
    uploader_name: Optional[str] = None
    file_name: str
    file_size: int
    mime_type: str
    is_public: bool
    processing_status: ProcessingStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentWithUrl(DocumentResponse):
    """Document response with signed URL"""
    download_url: str


class DocumentList(BaseModel):
    """List of documents"""
    documents: list[DocumentResponse]
    total: int


class TogglePublicRequest(BaseModel):
    """Request to toggle public status"""
    is_public: bool
