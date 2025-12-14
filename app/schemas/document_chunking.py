from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class DocumentChunkingCreateRequest(BaseModel):
    document_id: str
    template_id: str
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    agent_prompt: Optional[str] = None
    is_active: Optional[bool] = True
    is_public: bool = False


class DocumentChunkingUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_public: Optional[bool] = None
    agent_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class DocumentChunkingResponse(BaseModel):
    id: str
    user_id: str
    document_id: str
    template_id: str
    name: str
    description: Optional[str]
    agent_prompt: Optional[str]
    is_active: Optional[bool]
    is_public: bool
    created_at: datetime
    updated_at: Optional[datetime]
    uploader_name: Optional[str] = None
    document_name: Optional[str] = None
    template_name: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentChunkingCreateResponse(DocumentChunkingResponse):
    """Response for create operation - includes chunk info"""
    total_chunks: int
    sample_chunk: Optional[Dict[str, Any]] = None


class DocumentChunkingWithChunkCount(DocumentChunkingResponse):
    """For card display with chunk count"""
    chunk_count: int
    document_name: str
    template_name: str
    uploader_name: str
    sample_chunk: Optional[dict] = None


class DocumentChunkingListResponse(BaseModel):
    document_templates: List[DocumentChunkingWithChunkCount]
    total: int


class CheckExistsResponse(BaseModel):
    """For warning check in wizard Step 1"""
    exists: bool
    document_chunking_id: Optional[str] = None
    name: Optional[str] = None
