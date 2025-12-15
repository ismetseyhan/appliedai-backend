"""
RAG Prompt Service - Business logic for RAG prompt management.
"""
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.repositories.document_chunking_repository import DocumentChunkingRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.user_preferences_service import UserPreferencesService
from app.services.rag_prompt_generator_service import RagPromptGeneratorService
from app.schemas.rag_prompt import (
    RagPromptGenerationResponse,
    ActiveRagDataResponse,
    AvailableRagConfigsResponse
)


class RagPromptService:
    """Service for RAG prompt business logic."""

    def __init__(
        self,
        db: Session,
        preferences_service: UserPreferencesService
    ):
        self.chunking_repository = DocumentChunkingRepository(db)
        self.chunk_repository = DocumentChunkRepository(db)
        self.preferences_service = preferences_service

    async def generate_prompt(
        self,
        user_id: str,
        document_chunking_id: str,
        generator: RagPromptGeneratorService
    ) -> RagPromptGenerationResponse:
        """Generate RAG agent prompt for selected document_chunking config."""
        # 1. Validate access to document_chunking
        doc_chunking = self.chunking_repository.get_by_id(
            document_chunking_id, load_relations=True
        )

        if not doc_chunking:
            raise HTTPException(status_code=404, detail="Document chunking not found")

        if doc_chunking.user_id != user_id and not doc_chunking.is_public:
            raise HTTPException(status_code=403, detail="Access denied")

        # 2. Check chunks exist
        chunk_count = self.chunk_repository.count_by_document_chunking_id(
            document_chunking_id
        )

        if chunk_count == 0:
            raise HTTPException(status_code=400, detail="No chunks found for this configuration")

        # 3. Generate prompt
        prompt = await generator.generate_prompt(document_chunking_id)

        # 4. Save to database and mark as RAG Ready
        doc_chunking.agent_prompt = prompt
        doc_chunking.is_active = True
        self.chunking_repository.update(doc_chunking)

        return RagPromptGenerationResponse(
            document_chunking_id=doc_chunking.id,
            document_name=doc_chunking.document.file_name,
            chunking_name=doc_chunking.name,
            prompt=prompt,
            generated_at=datetime.now()
        )

    def get_prompt_by_id(
        self,
        user_id: str,
        document_chunking_id: str
    ) -> ActiveRagDataResponse:
        """Get RAG prompt for a specific config."""
        doc_chunking = self.chunking_repository.get_by_id(
            document_chunking_id, load_relations=True
        )

        if not doc_chunking:
            raise HTTPException(status_code=404, detail="Document chunking not found")

        # Check access
        if doc_chunking.user_id != user_id and not doc_chunking.is_public:
            raise HTTPException(status_code=403, detail="Access denied")

        if not doc_chunking.agent_prompt:
            raise HTTPException(status_code=404, detail="Prompt not generated yet")

        chunk_count = self.chunk_repository.count_by_document_chunking_id(
            document_chunking_id
        )

        return ActiveRagDataResponse(
            document_chunking_id=doc_chunking.id,
            document_name=doc_chunking.document.file_name,
            chunking_name=doc_chunking.name,
            prompt=doc_chunking.agent_prompt,
            chunk_count=chunk_count,
            is_own=(doc_chunking.user_id == user_id),
            updated_at=doc_chunking.updated_at
        )

    def get_active_prompt(
        self,
        user_id: str
    ) -> ActiveRagDataResponse:
        """Get current active RAG data configuration."""
        active_id = self.preferences_service.get_or_auto_select_rag_data(user_id)

        if not active_id:
            raise HTTPException(status_code=404, detail="No RAG data configured")

        doc_chunking = self.chunking_repository.get_by_id(
            active_id, load_relations=True
        )

        if not doc_chunking or not doc_chunking.agent_prompt:
            raise HTTPException(status_code=404, detail="Active RAG data not found or missing prompt")

        chunk_count = self.chunk_repository.count_by_document_chunking_id(active_id)

        return ActiveRagDataResponse(
            document_chunking_id=doc_chunking.id,
            document_name=doc_chunking.document.file_name,
            chunking_name=doc_chunking.name,
            prompt=doc_chunking.agent_prompt,
            chunk_count=chunk_count,
            is_own=(doc_chunking.user_id == user_id),
            updated_at=doc_chunking.updated_at
        )

    def update_active_prompt(
        self,
        user_id: str,
        new_prompt: str
    ) -> ActiveRagDataResponse:
        """Update RAG prompt (user edits)."""
        active_id = self.preferences_service.get_active_rag_data(user_id)

        if not active_id:
            raise HTTPException(status_code=404, detail="No active RAG data")

        doc_chunking = self.chunking_repository.get_by_id(
            active_id, load_relations=True
        )

        # Only owner can edit prompt
        if doc_chunking.user_id != user_id:
            raise HTTPException(status_code=403, detail="Only owner can edit prompt")

        doc_chunking.agent_prompt = new_prompt
        self.chunking_repository.update(doc_chunking)

        chunk_count = self.chunk_repository.count_by_document_chunking_id(active_id)

        return ActiveRagDataResponse(
            document_chunking_id=doc_chunking.id,
            document_name=doc_chunking.document.file_name,
            chunking_name=doc_chunking.name,
            prompt=doc_chunking.agent_prompt,
            chunk_count=chunk_count,
            is_own=True,
            updated_at=doc_chunking.updated_at
        )

    def get_available_configs(
        self,
        user_id: str
    ) -> AvailableRagConfigsResponse:
        """Get all available RAG configs (is_active=true, accessible)."""
        current_id = self.preferences_service.get_active_rag_data(user_id)

        # Query all configs accessible to user
        configs = self.chunking_repository.get_accessible_chunkings(
            user_id, load_relations=True
        )

        result = []
        for config in configs:
            chunk_count = self.chunk_repository.count_by_document_chunking_id(config.id)

            # Only include configs that have chunks
            if chunk_count > 0:
                result.append({
                    "id": config.id,
                    "name": config.name,
                    "document_name": config.document.file_name,
                    "chunk_count": chunk_count,
                    "is_own": config.user_id == user_id,
                    "is_public": config.is_public,
                    "is_current": config.id == current_id,
                    "is_active": config.is_active,
                    "has_prompt": config.agent_prompt is not None
                })

        return AvailableRagConfigsResponse(
            configs=result,
            current_id=current_id
        )

    def activate_config(
        self,
        user_id: str,
        document_chunking_id: str
    ) -> Dict[str, Any]:
        """Set a config as active RAG data source."""
        doc_chunking = self.chunking_repository.get_by_id_if_active_and_accessible(
            document_chunking_id, user_id
        )

        if not doc_chunking:
            raise HTTPException(status_code=404, detail="Config not found or not RAG ready")

        # Save to preferences
        self.preferences_service.set_active_rag_data(user_id, document_chunking_id)

        return {
            "message": "RAG data source activated",
            "document_chunking_id": document_chunking_id
        }
