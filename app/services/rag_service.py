from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_chunking_repository import DocumentChunkingRepository
from app.services.llm_service import LLMService
from app.services.user_preferences_service import UserPreferencesService
from app.schemas.rag import RAGRequest, RAGResponse
from app.agents.rag_agent import RAGAgent


class RAGService:
    """Service for RAG agent business logic."""

    def __init__(
            self,
            db: Session,
            llm_service: LLMService,
            preferences_service: UserPreferencesService
    ):
        self.db = db
        self.llm_service = llm_service
        self.preferences_service = preferences_service
        self.chunk_repository = DocumentChunkRepository(db)
        self.chunking_repository = DocumentChunkingRepository(db)

    async def query(self, user_id: str, request: RAGRequest) -> RAGResponse:
        """Execute RAG query with validation and agent initialization."""
        active_id = self.preferences_service.get_or_auto_select_rag_data(user_id, self.db)
        if not active_id:
            raise HTTPException(
                status_code=404,
                detail="No active RAG data source. Please upload and activate a document."
            )

        doc_chunking = self.chunking_repository.get_by_id(active_id)
        if not doc_chunking:
            raise HTTPException(
                status_code=404,
                detail="Document chunking not found"
            )

        if not doc_chunking.agent_prompt:
            raise HTTPException(
                status_code=400,
                detail="RAG agent prompt not generated. Generate prompt first."
            )

        agent = RAGAgent(
            chunk_repository=self.chunk_repository,
            llm_service=self.llm_service,
            document_chunking_id=active_id,
            agent_prompt=doc_chunking.agent_prompt
        )

        response = await agent.query(request.query, request.top_k)
        return response
