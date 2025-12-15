"""
Orchestrator API Endpoints
Multi-agent orchestration for queries.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user, get_orchestrator_service
from app.schemas.orchestrator import (
    OrchestratorQueryRequest,
    OrchestratorQueryResponse
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
    Automatically creates or uses existing conversation.
    """
    try:
        response = await orchestrator_service.execute_query(
            user_id=current_user.id,
            request=request
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")
