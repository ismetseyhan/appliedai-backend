"""
Orchestrator API Endpoints
Multi-agent orchestration and conversation management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.api.deps import get_current_user, get_orchestrator_service
from app.schemas.orchestrator import (
    OrchestratorQueryRequest,
    OrchestratorQueryResponse,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationListResponse
)
from app.services.orchestrator_service import OrchestratorService
from app.entities.user import User


router = APIRouter()


@router.post(
    "/query",
    response_model=OrchestratorQueryResponse,
    summary="Execute orchestrated multi-agent query"
)
async def execute_orchestrated_query(
    request: OrchestratorQueryRequest,
    current_user: User = Depends(get_current_user),
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service)
):
    """
    Execute a query using multi-agent orchestration.
    """
    try:
        response = await orchestrator_service.execute_query(
            user_id=current_user.id,
            request=request
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    summary="Create a new conversation"
)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service)
):
    try:
        response = orchestrator_service.create_conversation(
            user_id=current_user.id,
            request=request
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List user's conversations"
)
async def list_conversations(
    limit: int = Query(50, ge=1, le=100, description="Number of conversations to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service)
):
    try:
        response = orchestrator_service.get_user_conversations(
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation details with messages"
)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service)
):
    response = orchestrator_service.get_conversation_detail(
        user_id=current_user.id,
        conversation_id=conversation_id
    )

    if not response:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return response


@router.delete(
    "/conversations/{conversation_id}",
    summary="Delete a conversation"
)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service)
):
    success = orchestrator_service.delete_conversation(
        user_id=current_user.id,
        conversation_id=conversation_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Conversation deleted successfully"}
