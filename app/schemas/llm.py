"""
LLM Schemas - request/response models.
"""
from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(description="Message content")


class ChatRequest(BaseModel):
    """Chat completion request"""
    message: str = Field(description="User message", min_length=1)
    system_prompt: Optional[str] = Field(None, description="Optional system prompt")
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens to generate")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What are the top 10 highest rated movies?",
                "system_prompt": "You are a helpful SQL assistant.",
                "temperature": 0.7,
                "max_tokens": 500
            }
        }


class ChatResponse(BaseModel):
    """Chat completion response"""
    response: str = Field(description="AI response")
    model: str = Field(description="Model used")
    user_message: str = Field(description="Original user message")
