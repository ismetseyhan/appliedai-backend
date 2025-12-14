from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.entities.document_chunk import DocumentChunk
from app.entities.document import Document
from app.entities.parsing_template import ParsingTemplate
from app.entities.user import User
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.firebase_storage_service import FirebaseStorageService
from app.services.pdf_extraction_service import PDFExtractionService
from app.services.template_parser_service import TemplateParserService
from app.services.llm_service import LLMService


class ChunkingProcessorService:
    def __init__(self, db: Session, storage_service: FirebaseStorageService, llm_service: LLMService):
        self.db = db
        self.storage_service = storage_service
        self.llm_service = llm_service
        self.chunk_repository = DocumentChunkRepository(db)

    async def chunk_document_by_id(
        self,
        document_id: str,
        template_id: str,
        current_user: User,
        document_chunking_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse document and create chunks with embeddings."""
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if document.user_id != current_user.id and not document.is_public:
            raise HTTPException(status_code=403, detail="Access denied")

        template = self.db.query(ParsingTemplate).filter(ParsingTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if template.user_id != current_user.id and not template.is_public:
            raise HTTPException(status_code=403, detail="Template access denied")

        if document_chunking_id:
            existing_count = self.chunk_repository.delete_by_document_chunking_id(document_chunking_id)
            if existing_count > 0:
                print(f"Deleted {existing_count} existing chunks for document_chunking {document_chunking_id}")

            return await self.chunk_document(document, template, document_chunking_id)
        else:
            return await self.chunk_document(document, template, None)

    async def chunk_document(
        self,
        document: Document,
        template: ParsingTemplate,
        document_chunking_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process PDF: extract text, parse records, create embeddings, save chunks."""
        pdf_bytes = self.storage_service.download_file(document.storage_path)
        if not pdf_bytes:
            raise Exception("Failed to download PDF")

        full_text = PDFExtractionService.extract_text_from_bytes(pdf_bytes, max_pages=None)

        template_json = template.template_json
        parsed_records = TemplateParserService.parse_pdf(full_text, template_json)

        if not parsed_records or len(parsed_records) == 0:
            raise Exception("No records parsed")

        chunks = []
        for idx, record in enumerate(parsed_records):
            chunk_data = await self._build_chunk(document_chunking_id, template, record, idx)
            chunks.append(chunk_data)

        if document_chunking_id:
            print(f"[ChunkingProcessor] Saving {len(chunks)} chunks with document_chunking_id={document_chunking_id}")
            saved_chunks = self.chunk_repository.bulk_create(chunks)
            print(f"[ChunkingProcessor] Successfully saved {len(saved_chunks)} chunks")
            sample_chunk = self._chunk_to_dict(saved_chunks[0]) if saved_chunks else None
        else:
            print(f"[ChunkingProcessor] Preview mode: NOT saving {len(chunks)} chunks")
            sample_chunk = self._chunk_to_dict_preview(chunks[0]) if chunks else None

        return {"total_chunks": len(chunks), "sample_chunk": sample_chunk}

    async def _build_chunk(
        self,
        document_chunking_id: Optional[str],
        template: ParsingTemplate,
        record: Dict[str, Any],
        record_index: int
    ) -> DocumentChunk:
        """Build chunk with metadata, LLM text, embedding text, and vector."""
        chunk_metadata = self._extract_metadata(record, template.metadata_keywords)
        llm_text = self._build_llm_text(record, template.llm_text)
        embedding_text = self._build_embedding_text(record, template.embedding_text)
        embedding_vector = await self.llm_service.create_embedding(embedding_text)

        chunk = DocumentChunk(
            record_index=record_index,
            raw_object=record,
            llm_text=llm_text,
            embedding_text=embedding_text,
            embedding=embedding_vector,
            chunk_metadata=chunk_metadata
        )

        if document_chunking_id:
            chunk.document_chunking_id = document_chunking_id

        return chunk

    def _extract_metadata(self, record: Dict[str, Any], metadata_keywords: Optional[List[str]]) -> Dict[str, Any]:
        if not metadata_keywords:
            return {}
        return {key: record[key] for key in metadata_keywords if key in record}

    def _build_llm_text(self, record: Dict[str, Any], llm_text_fields: Optional[List[str]]) -> str:
        if not llm_text_fields:
            return ""
        parts = [self._format_value(record.get(field)) for field in llm_text_fields if record.get(field)]
        return " ".join(parts)

    def _build_embedding_text(self, record: Dict[str, Any], embedding_text_fields: Optional[List[str]]) -> str:
        if not embedding_text_fields:
            return ""
        parts = []
        for field_key in embedding_text_fields:
            value = record.get(field_key)
            if value:
                parts.append(f"{field_key}: {self._format_value(value)}")
        return ", ".join(parts)

    def _format_value(self, value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item)
        return str(value)

    def _chunk_to_dict(self, chunk: DocumentChunk) -> Dict[str, Any]:
        return {
            "id": chunk.id,
            "record_index": chunk.record_index,
            "llm_text": chunk.llm_text,
            "embedding_text": chunk.embedding_text,
            "metadata": chunk.chunk_metadata,
            "embedding_dimensions": len(chunk.embedding) if chunk.embedding is not None else 0
        }

    def _chunk_to_dict_preview(self, chunk: DocumentChunk) -> Dict[str, Any]:
        return {
            "id": "preview",
            "record_index": chunk.record_index,
            "llm_text": chunk.llm_text,
            "embedding_text": chunk.embedding_text,
            "metadata": chunk.chunk_metadata,
            "embedding_dimensions": len(chunk.embedding) if chunk.embedding is not None else 0
        }
