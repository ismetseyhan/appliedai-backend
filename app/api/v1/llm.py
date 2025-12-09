"""
LLM Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_llm_service, get_current_user
from app.schemas.llm import ChatRequest, ChatResponse
from app.services.llm_service import LLMService
from app.entities.user import User

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    llm_service: LLMService = Depends(get_llm_service),
    current_user: User = Depends(get_current_user)
):
    try:

        messages = []

        # Add system prompt if provided
        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt
            })

        # Add user message
        messages.append({
            "role": "user",
            "content": request.message
        })

        #  LLM service
        response_text = await llm_service.achat_completion(
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        return ChatResponse(
            response=response_text,
            model=llm_service.model_name,
            user_message=request.message
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM service error: {str(e)}"
        )


@router.get("/health")
async def llm_health(
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    Check LLM service health
    """
    return {
        "status": "healthy",
        "model": llm_service.model_name,
        "base_url": llm_service.base_url,
        "api_key_configured": bool(llm_service.api_key and llm_service.api_key.startswith("sk-"))
    }
