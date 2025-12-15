from fastapi import APIRouter, Depends
from app.api.deps import (
    get_current_user,
    get_rag_prompt_service,
    get_rag_prompt_generator_service
)
from app.entities.user import User
from app.schemas.rag_prompt import (
    RagPromptGenerationRequest,
    RagPromptGenerationResponse,
    RagPromptUpdateRequest,
    ActiveRagDataResponse,
    AvailableRagConfigsResponse
)
from app.services.rag_prompt_generator_service import RagPromptGeneratorService
from app.services.rag_prompt_service import RagPromptService

router = APIRouter()


@router.post("/generate", response_model=RagPromptGenerationResponse)
async def generate_rag_prompt(
    request: RagPromptGenerationRequest,
    current_user: User = Depends(get_current_user),
    rag_prompt_service: RagPromptService = Depends(get_rag_prompt_service),
    generator: RagPromptGeneratorService = Depends(get_rag_prompt_generator_service)
):
    """Generate RAG agent prompt for selected document_chunking config."""
    return await rag_prompt_service.generate_prompt(
        user_id=current_user.id,
        document_chunking_id=request.document_chunking_id,
        generator=generator
    )


@router.get("/config/{document_chunking_id}", response_model=ActiveRagDataResponse)
async def get_rag_prompt_by_id(
    document_chunking_id: str,
    current_user: User = Depends(get_current_user),
    rag_prompt_service: RagPromptService = Depends(get_rag_prompt_service)
):
    """Get RAG prompt for a specific config."""
    return rag_prompt_service.get_prompt_by_id(
        user_id=current_user.id,
        document_chunking_id=document_chunking_id
    )


@router.get("/active", response_model=ActiveRagDataResponse)
async def get_active_rag_data(
    current_user: User = Depends(get_current_user),
    rag_prompt_service: RagPromptService = Depends(get_rag_prompt_service)
):
    """Get current active RAG data configuration."""
    return rag_prompt_service.get_active_prompt(user_id=current_user.id)


@router.patch("/active", response_model=ActiveRagDataResponse)
async def update_rag_prompt(
    request: RagPromptUpdateRequest,
    current_user: User = Depends(get_current_user),
    rag_prompt_service: RagPromptService = Depends(get_rag_prompt_service)
):
    """Update RAG prompt (user edits)."""
    return rag_prompt_service.update_active_prompt(
        user_id=current_user.id,
        new_prompt=request.prompt
    )


@router.get("/available", response_model=AvailableRagConfigsResponse)
async def get_available_rag_configs(
    current_user: User = Depends(get_current_user),
    rag_prompt_service: RagPromptService = Depends(get_rag_prompt_service)
):
    """Get all available RAG configs (is_active=true, accessible)."""
    return rag_prompt_service.get_available_configs(user_id=current_user.id)


@router.post("/activate/{document_chunking_id}")
async def activate_rag_config(
    document_chunking_id: str,
    current_user: User = Depends(get_current_user),
    rag_prompt_service: RagPromptService = Depends(get_rag_prompt_service)
):
    """Set a config as active RAG data source."""
    return rag_prompt_service.activate_config(
        user_id=current_user.id,
        document_chunking_id=document_chunking_id
    )
