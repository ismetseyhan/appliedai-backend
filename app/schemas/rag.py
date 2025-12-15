"""
RAG Agent Schemas
Request/response models for Retrieval-Augmented Generation.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class RAGRequest(BaseModel):
    """Request schema for RAG query"""
    query: str = Field(min_length=1, description="Natural language query")
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Find Crime movies about detectives",
                "top_k": 5
            }
        }


class RetrievedChunk(BaseModel):
    """Single retrieved chunk with score"""
    id: str
    score: float
    llm_text: str
    metadata: Dict[str, Any]


class AgentStep(BaseModel):
    """Single step in agent reasoning process"""
    step_number: int
    action: str
    action_input: str
    observation: str


class RAGResponse(BaseModel):
    """Response schema for RAG query"""
    query: str
    final_answer: str
    chunks: List[RetrievedChunk]
    mode_used: str
    filters_applied: bool
    steps: List[AgentStep]
    execution_time_ms: int

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Find Crime movies about detectives",
                "final_answer": "Based on the retrieved records, here are Crime movies about detectives...",
                "chunks": [
                    {
                        "id": "chunk-uuid",
                        "score": 0.8932,
                        "llm_text": "Se7en is a Crime/Thriller movie...",
                        "metadata": {"movie_id": 101, "movie_name": "Se7en", "genres": ["Crime", "Thriller"]}
                    }
                ],
                "mode_used": "hybrid",
                "filters_applied": True,
                "steps": [
                    {
                        "step_number": 1,
                        "action": "retrieve_records",
                        "action_input": "{\"query\": \"detectives\", \"mode\": \"hybrid\", \"metadata_filter\": {...}}",
                        "observation": "Retrieved 5 chunks with scores 0.89-0.76"
                    }
                ],
                "execution_time_ms": 3420
            }
        }
