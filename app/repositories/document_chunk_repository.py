from typing import List, Optional, Any
from sqlalchemy.orm import Session
from app.entities.document_chunk import DocumentChunk


class DocumentChunkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, chunk: DocumentChunk) -> DocumentChunk:
        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    def bulk_create(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        self.db.add_all(chunks)
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

    def get_by_document_chunking_id(self, document_chunking_id: str) -> list[type[DocumentChunk]]:
        """Get chunks by document_chunking_id."""
        return self.db.query(DocumentChunk).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        ).order_by(DocumentChunk.record_index).all()

    def get_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        return self.db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()

    def delete_by_document_chunking_id(self, document_chunking_id: str) -> int:
        """Delete all chunks for a document chunking."""
        count = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        ).delete()
        self.db.commit()
        return count

    def count_by_document_chunking_id(self, document_chunking_id: str) -> int:
        """Count chunks by document_chunking_id."""
        return self.db.query(DocumentChunk).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        ).count()
