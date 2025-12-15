"""
Conversations API Endpoints
Conversation CRUD operations and message management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_conversation_service
from app.schemas.orchestrator import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationListResponse
)
from app.services.conversation_service import ConversationService
from app.entities.user import User


router = APIRouter()


@router.post(
    "",
    response_model=ConversationResponse,
    summary="Create a new conversation"
)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Create a new conversation for the current user."""
    try:
        response = conversation_service.create_conversation(
            user_id=current_user.id,
            request=request
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List user's conversations"
)
async def list_conversations(
    limit: int = Query(50, ge=1, le=100, description="Number of conversations to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """List all conversations for the current user with pagination."""
    try:
        response = conversation_service.get_user_conversations(
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation details with messages"
)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Get a specific conversation with all its messages."""
    response = conversation_service.get_conversation_detail(
        user_id=current_user.id,
        conversation_id=conversation_id
    )

    if not response:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return response


@router.delete(
    "/{conversation_id}",
    summary="Delete a conversation"
)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Delete a conversation and all its messages."""
    success = conversation_service.delete_conversation(
        user_id=current_user.id,
        conversation_id=conversation_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Conversation deleted successfully"}
