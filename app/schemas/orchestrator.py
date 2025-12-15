"""
Orchestrator Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class OrchestratorQueryRequest(BaseModel):
    """Request schema for orchestrated query"""
    conversation_id: Optional[str] = Field(None, description="Conversation ID for history tracking")
    query: str = Field(min_length=1, description="User's natural language query")
    max_iterations: int = Field(5, ge=1, le=10, description="Maximum agent iterations")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_abc123",
                "query": "What is Fight Club about and who produced it?",
                "max_iterations": 5
            }
        }


class AgentExecutionDetail(BaseModel):
    """Detailed execution information for a single agent"""
    agent_name: str
    steps: List[Dict[str, Any]]
    execution_time_ms: int
    result_summary: str
    specific_data: Optional[Dict[str, Any]] = None


class OrchestratorQueryResponse(BaseModel):
    """Response schema for orchestrated query"""
    query: str
    final_answer: str
    agents_called: List[str]
    mode_used: str
    agent_details: Dict[str, AgentExecutionDetail]
    execution_time_ms: int
    conversation_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is Fight Club about and who produced it?",
                "final_answer": "Fight Club is about... Produced by Art Linson...",
                "agents_called": ["rag_agent", "research_agent"],
                "mode_used": "sequential",
                "agent_details": {
                    "rag_agent": {
                        "agent_name": "rag_agent",
                        "steps": [{"step_number": 1, "action": "retrieve_records", "observation": "..."}],
                        "execution_time_ms": 3200,
                        "result_summary": "Found plot summary",
                        "specific_data": {"chunks": []}
                    }
                },
                "execution_time_ms": 5420,
                "conversation_id": "conv_abc123"
            }
        }


class ConversationCreateRequest(BaseModel):
    """Request schema for creating a new conversation"""
    title: str = Field(min_length=1, max_length=200, description="Conversation title")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Movie Information Questions"
            }
        }


class ConversationMessage(BaseModel):
    """Single message in a conversation"""
    id: str
    role: str
    content: str
    agent_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class ConversationResponse(BaseModel):
    """Response schema for a single conversation"""
    id: str
    user_id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "conv_abc123",
                "user_id": "user_xyz",
                "title": "Movie Questions",
                "message_count": 10,
                "created_at": "2025-12-15T10:00:00Z",
                "updated_at": "2025-12-15T11:30:00Z"
            }
        }


class ConversationDetailResponse(BaseModel):
    """Detailed conversation with messages"""
    id: str
    user_id: str
    title: str
    messages: List[ConversationMessage]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "conv_abc123",
                "user_id": "user_xyz",
                "title": "Movie Questions",
                "messages": [
                    {
                        "id": "msg_1",
                        "role": "user",
                        "content": "What is Fight Club about?",
                        "agent_metadata": None,
                        "created_at": "2025-12-15T10:00:00Z"
                    }
                ],
                "created_at": "2025-12-15T10:00:00Z",
                "updated_at": "2025-12-15T11:30:00Z"
            }
        }


class ConversationListResponse(BaseModel):
    """List of conversations with pagination"""
    conversations: List[ConversationResponse]
    total: int
    limit: int
    offset: int

    class Config:
        json_schema_extra = {
            "example": {
                "conversations": [],
                "total": 25,
                "limit": 50,
                "offset": 0
            }
        }
