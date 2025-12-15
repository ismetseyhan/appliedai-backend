from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict


class RagPromptGenerationRequest(BaseModel):
    """Request to generate RAG prompt for a chunking config."""
    document_chunking_id: str


class RagPromptGenerationResponse(BaseModel):
    """Response after generating RAG prompt."""
    document_chunking_id: str
    document_name: str
    chunking_name: str
    prompt: str
    generated_at: datetime


class RagPromptUpdateRequest(BaseModel):
    """Update RAG prompt (user edits)."""
    prompt: str = Field(min_length=10)


class ActiveRagDataResponse(BaseModel):
    """Current active RAG data configuration."""
    document_chunking_id: str
    document_name: str
    chunking_name: str
    prompt: str
    chunk_count: int
    is_own: bool
    updated_at: Optional[datetime]


class AvailableRagConfigsResponse(BaseModel):
    """List of available RAG configs (is_active=true, accessible)."""
    configs: List[Dict]
    current_id: Optional[str]
