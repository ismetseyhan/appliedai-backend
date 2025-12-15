from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime
from app.api.deps import get_current_user, get_db, get_llm_service
from app.entities.user import User
from app.entities.document_chunking import DocumentChunking
from app.entities.document_chunk import DocumentChunk
from app.schemas.rag_prompt import (
    RagPromptGenerationRequest,
    RagPromptGenerationResponse,
    RagPromptUpdateRequest,
    ActiveRagDataResponse,
    AvailableRagConfigsResponse
)
from app.services.rag_prompt_generator_service import RagPromptGeneratorService
from app.services.user_preferences_service import UserPreferencesService
from app.services.llm_service import LLMService
from app.repositories.user_preferences_repository import UserPreferencesRepository

router = APIRouter()


@router.post("/generate", response_model=RagPromptGenerationResponse)
async def generate_rag_prompt(
    request: RagPromptGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service)
):
    """Generate RAG agent prompt for selected document_chunking config."""
    # 1. Validate access to document_chunking
    doc_chunking = db.query(DocumentChunking).filter(
        DocumentChunking.id == request.document_chunking_id
    ).first()

    if not doc_chunking:
        raise HTTPException(status_code=404, detail="Document chunking not found")

    if doc_chunking.user_id != current_user.id and not doc_chunking.is_public:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Check chunks exist
    chunk_count = db.query(func.count(DocumentChunk.id)).filter(
        DocumentChunk.document_chunking_id == request.document_chunking_id
    ).scalar()

    if chunk_count == 0:
        raise HTTPException(status_code=400, detail="No chunks found for this configuration")

    # 3. Generate prompt
    generator = RagPromptGeneratorService(llm_service)
    prompt = await generator.generate_prompt(request.document_chunking_id, db)

    # 4. Save to database
    doc_chunking.agent_prompt = prompt
    doc_chunking.is_active = True  # Mark as RAG Ready
    db.commit()

    return RagPromptGenerationResponse(
        document_chunking_id=doc_chunking.id,
        document_name=doc_chunking.document.file_name,
        chunking_name=doc_chunking.name,
        prompt=prompt,
        generated_at=datetime.now()
    )


@router.get("/config/{document_chunking_id}", response_model=ActiveRagDataResponse)
async def get_rag_prompt_by_id(
    document_chunking_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get RAG prompt for a specific config."""
    doc_chunking = db.query(DocumentChunking).filter(
        DocumentChunking.id == document_chunking_id
    ).first()

    if not doc_chunking:
        raise HTTPException(status_code=404, detail="Document chunking not found")

    # Check access
    if doc_chunking.user_id != current_user.id and not doc_chunking.is_public:
        raise HTTPException(status_code=403, detail="Access denied")

    if not doc_chunking.agent_prompt:
        raise HTTPException(status_code=404, detail="Prompt not generated yet")

    chunk_count = db.query(func.count(DocumentChunk.id)).filter(
        DocumentChunk.document_chunking_id == document_chunking_id
    ).scalar()

    return ActiveRagDataResponse(
        document_chunking_id=doc_chunking.id,
        document_name=doc_chunking.document.file_name,
        chunking_name=doc_chunking.name,
        prompt=doc_chunking.agent_prompt,
        chunk_count=chunk_count,
        is_own=(doc_chunking.user_id == current_user.id),
        updated_at=doc_chunking.updated_at
    )


@router.get("/active", response_model=ActiveRagDataResponse)
async def get_active_rag_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current active RAG data configuration."""
    prefs_repository = UserPreferencesRepository(db)
    prefs_service = UserPreferencesService(prefs_repository)
    active_id = prefs_service.get_or_auto_select_rag_data(current_user.id, db)

    if not active_id:
        raise HTTPException(status_code=404, detail="No RAG data configured")

    doc_chunking = db.query(DocumentChunking).filter(
        DocumentChunking.id == active_id
    ).first()

    if not doc_chunking or not doc_chunking.agent_prompt:
        raise HTTPException(status_code=404, detail="Active RAG data not found or missing prompt")

    chunk_count = db.query(func.count(DocumentChunk.id)).filter(
        DocumentChunk.document_chunking_id == active_id
    ).scalar()

    return ActiveRagDataResponse(
        document_chunking_id=doc_chunking.id,
        document_name=doc_chunking.document.file_name,
        chunking_name=doc_chunking.name,
        prompt=doc_chunking.agent_prompt,
        chunk_count=chunk_count,
        is_own=(doc_chunking.user_id == current_user.id),
        updated_at=doc_chunking.updated_at
    )


@router.patch("/active", response_model=ActiveRagDataResponse)
async def update_rag_prompt(
    request: RagPromptUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update RAG prompt (user edits)."""
    prefs_repository = UserPreferencesRepository(db)
    prefs_service = UserPreferencesService(prefs_repository)
    active_id = prefs_service.get_active_rag_data(current_user.id)

    if not active_id:
        raise HTTPException(status_code=404, detail="No active RAG data")

    doc_chunking = db.query(DocumentChunking).filter(
        DocumentChunking.id == active_id
    ).first()

    # Only owner can edit prompt
    if doc_chunking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can edit prompt")

    doc_chunking.agent_prompt = request.prompt
    db.commit()

    chunk_count = db.query(func.count(DocumentChunk.id)).filter(
        DocumentChunk.document_chunking_id == active_id
    ).scalar()

    return ActiveRagDataResponse(
        document_chunking_id=doc_chunking.id,
        document_name=doc_chunking.document.file_name,
        chunking_name=doc_chunking.name,
        prompt=doc_chunking.agent_prompt,
        chunk_count=chunk_count,
        is_own=True,
        updated_at=doc_chunking.updated_at
    )


@router.get("/available", response_model=AvailableRagConfigsResponse)
async def get_available_rag_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all available RAG configs (is_active=true, accessible)."""
    prefs_repository = UserPreferencesRepository(db)
    prefs_service = UserPreferencesService(prefs_repository)
    current_id = prefs_service.get_active_rag_data(current_user.id)

    # Query all configs with chunks (regardless of is_active)
    configs = db.query(DocumentChunking).filter(
        or_(
            DocumentChunking.user_id == current_user.id,
            DocumentChunking.is_public == True
        )
    ).all()

    result = []
    for config in configs:
        chunk_count = db.query(func.count(DocumentChunk.id)).filter(
            DocumentChunk.document_chunking_id == config.id
        ).scalar()

        # Only include configs that have chunks
        if chunk_count > 0:
            result.append({
                "id": config.id,
                "name": config.name,
                "document_name": config.document.file_name,
                "chunk_count": chunk_count,
                "is_own": config.user_id == current_user.id,
                "is_public": config.is_public,
                "is_current": config.id == current_id,
                "is_active": config.is_active,  # Added to show RAG Ready status
                "has_prompt": config.agent_prompt is not None  # Added to show if prompt exists
            })

    return AvailableRagConfigsResponse(
        configs=result,
        current_id=current_id
    )


@router.post("/activate/{document_chunking_id}")
async def activate_rag_config(
    document_chunking_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set a config as active RAG data source."""
    doc_chunking = db.query(DocumentChunking).filter(
        DocumentChunking.id == document_chunking_id,
        DocumentChunking.is_active == True
    ).first()

    if not doc_chunking:
        raise HTTPException(status_code=404, detail="Config not found or not RAG ready")

    # Check access
    if doc_chunking.user_id != current_user.id and not doc_chunking.is_public:
        raise HTTPException(status_code=403, detail="Access denied")

    # Save to preferences
    prefs_repository = UserPreferencesRepository(db)
    prefs_service = UserPreferencesService(prefs_repository)
    prefs_service.set_active_rag_data(current_user.id, document_chunking_id)

    return {"message": "RAG data source activated", "document_chunking_id": document_chunking_id}
