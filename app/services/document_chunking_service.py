from typing import Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.entities.document_chunking import DocumentChunking
from app.entities.user import User
from app.schemas.document_chunking import (
    DocumentChunkingCreateRequest,
    DocumentChunkingUpdateRequest,
    DocumentChunkingResponse,
    DocumentChunkingCreateResponse,
    DocumentChunkingListResponse,
    DocumentChunkingWithChunkCount,
    CheckExistsResponse
)
from app.repositories.document_chunking_repository import DocumentChunkingRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.parsing_template_repository import ParsingTemplateRepository
from app.entities.document_chunk import DocumentChunk
from app.services.chunking_processor_service import ChunkingProcessorService


class DocumentChunkingService:

    def __init__(self, db: Session, chunking_processor: ChunkingProcessorService = None):
        self.db = db
        self.doc_template_repo = DocumentChunkingRepository(db)
        self.document_repo = DocumentRepository(db)
        self.template_repo = ParsingTemplateRepository(db)
        self.chunking_processor = chunking_processor

    async def create_document_chunking(
            self,
            request: DocumentChunkingCreateRequest,
            current_user: User
    ) -> DocumentChunkingCreateResponse:
        """Create document chunking configuration and process chunks."""
        if not self.chunking_processor:
            raise HTTPException(status_code=500, detail="Chunking processor not available")

        document = self.document_repo.get_by_id(request.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if document.user_id != current_user.id and not document.is_public:
            raise HTTPException(status_code=403, detail="Access denied to document")

        template = self.template_repo.get_by_id(request.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if template.user_id != current_user.id and not template.is_public:
            raise HTTPException(status_code=403, detail="Access denied to template")

        existing = self.doc_template_repo.get_by_document_id(request.document_id, current_user.id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Document chunking already exists for this document: '{existing.name}'"
            )

        doc_template = DocumentChunking(
            user_id=current_user.id,
            document_id=request.document_id,
            template_id=request.template_id,
            name=request.name,
            description=request.description,
            agent_prompt=request.agent_prompt,
            is_active=request.is_active,
            is_public=request.is_public
        )

        try:
            created = self.doc_template_repo.create(doc_template)
            print(f"[DocumentChunkingService] Created DocumentChunking with ID: {created.id}")

            print(f"[DocumentChunkingService] Calling ChunkingProcessor...")
            try:
                chunk_result = await self.chunking_processor.chunk_document_by_id(
                    document_id=request.document_id,
                    template_id=request.template_id,
                    current_user=current_user,
                    document_chunking_id=created.id
                )
                print(f"[DocumentChunkingService] ChunkingProcessor completed")
            except Exception as chunk_error:
                print(f"[DocumentChunkingService] ChunkingProcessor FAILED: {str(chunk_error)}")
                import traceback
                traceback.print_exc()
                raise

            base_response = self._to_response(created)
            return DocumentChunkingCreateResponse(
                **base_response.model_dump(),
                total_chunks=chunk_result.get("total_chunks", 0),
                sample_chunk=chunk_result.get("sample_chunk")
            )
        except IntegrityError:
            raise HTTPException(
                status_code=400,
                detail="Document chunking already exists for this document"
            )

    def list_document_chunking_processes(self, current_user: User) -> DocumentChunkingListResponse:
        """List all document chunking processes accessible to user (own + public)."""
        results = self.doc_template_repo.get_with_chunk_count(current_user.id)

        templates_with_counts = []
        for doc_template, chunk_count, document_name, template_name, uploader_name in results:
            sample_chunk = None
            if chunk_count and chunk_count > 0:
                chunk = self.db.query(DocumentChunk).filter(
                    DocumentChunk.document_chunking_id == doc_template.id
                ).order_by(DocumentChunk.record_index).first()

                if chunk:
                    sample_chunk = {
                        "id": chunk.id,
                        "record_index": chunk.record_index,
                        "llm_text": chunk.llm_text,
                        "embedding_text": chunk.embedding_text,
                        "metadata": chunk.chunk_metadata or {},
                        "embedding_dimensions": len(chunk.embedding) if chunk.embedding is not None else 0
                    }

            templates_with_counts.append(
                DocumentChunkingWithChunkCount(
                    id=doc_template.id,
                    user_id=doc_template.user_id,
                    document_id=doc_template.document_id,
                    template_id=doc_template.template_id,
                    name=doc_template.name,
                    description=doc_template.description,
                    agent_prompt=doc_template.agent_prompt,
                    is_active=doc_template.is_active,
                    is_public=doc_template.is_public,
                    created_at=doc_template.created_at,
                    updated_at=doc_template.updated_at,
                    chunk_count=chunk_count or 0,
                    document_name=document_name,
                    template_name=template_name,
                    uploader_name=uploader_name,
                    sample_chunk=sample_chunk
                )
            )

        return DocumentChunkingListResponse(
            document_templates=templates_with_counts,
            total=len(templates_with_counts)
        )

    def check_exists_for_document(
            self,
            document_id: str,
            current_user: User
    ) -> CheckExistsResponse:
        """Check if document chunking exists for this document."""
        existing = self.doc_template_repo.get_by_document_id(document_id, current_user.id)

        return CheckExistsResponse(
            exists=existing is not None,
            document_chunking_id=existing.id if existing else None,
            name=existing.name if existing else None
        )

    def get_by_id(
            self,
            template_id: str,
            current_user: User
    ) -> DocumentChunkingResponse:
        """Get document chunking by ID."""
        doc_template = self.doc_template_repo.get_by_id(template_id, load_relations=True)
        if not doc_template:
            raise HTTPException(status_code=404, detail="Document chunking not found")

        if doc_template.user_id != current_user.id and not doc_template.is_public:
            raise HTTPException(status_code=403, detail="Access denied")

        return self._to_response(doc_template)

    def update_document_chunking_detail(
            self,
            template_id: str,
            request: DocumentChunkingUpdateRequest,
            current_user: User
    ) -> DocumentChunkingResponse:
        """Update document chunking configuration."""
        doc_template = self.doc_template_repo.get_by_id(template_id)
        if not doc_template:
            raise HTTPException(status_code=404, detail="Document chunking not found")

        if doc_template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only owner can update")

        if request.name is not None:
            doc_template.name = request.name
        if request.description is not None:
            doc_template.description = request.description
        if request.is_public is not None:
            doc_template.is_public = request.is_public
        if request.agent_prompt is not None:
            doc_template.agent_prompt = request.agent_prompt
        if request.is_active is not None:
            doc_template.is_active = request.is_active

        updated = self.doc_template_repo.update(doc_template)
        return self._to_response(updated)

    def delete_document_chunking_processes(
            self,
            template_id: str,
            current_user: User
    ) -> None:
        """Delete document chunking (cascades to chunks)."""
        doc_template = self.doc_template_repo.get_by_id(template_id)
        if not doc_template:
            raise HTTPException(status_code=404, detail="Document chunking not found")

        if doc_template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only owner can delete")

        self.doc_template_repo.delete(doc_template)

    def _to_response(self, doc_template: DocumentChunking) -> DocumentChunkingResponse:
        return DocumentChunkingResponse(
            id=doc_template.id,
            user_id=doc_template.user_id,
            document_id=doc_template.document_id,
            template_id=doc_template.template_id,
            name=doc_template.name,
            description=doc_template.description,
            agent_prompt=doc_template.agent_prompt,
            is_active=doc_template.is_active,
            is_public=doc_template.is_public,
            created_at=doc_template.created_at,
            updated_at=doc_template.updated_at,
            uploader_name=doc_template.user.display_name if doc_template.user else None,
            document_name=doc_template.document.file_name if doc_template.document else None,
            template_name=doc_template.parsing_template.template_name if doc_template.parsing_template else None
        )
