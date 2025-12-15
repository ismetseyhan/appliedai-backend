from typing import Optional, List, Tuple, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from app.entities.document_chunking import DocumentChunking
from app.entities.document_chunk import DocumentChunk
from app.entities.document import Document
from app.entities.parsing_template import ParsingTemplate
from app.entities.user import User


class DocumentChunkingRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, doc_chunking: DocumentChunking) -> DocumentChunking:
        self.db.add(doc_chunking)
        self.db.commit()
        self.db.refresh(doc_chunking)
        return doc_chunking

    def get_by_id(self, chunking_id: str, load_relations: bool = False) -> Optional[DocumentChunking]:
        query = self.db.query(DocumentChunking)
        if load_relations:
            query = query.options(
                joinedload(DocumentChunking.user),
                joinedload(DocumentChunking.document),
                joinedload(DocumentChunking.parsing_template)
            )
        return query.filter(DocumentChunking.id == chunking_id).first()

    def get_by_document_id(self, document_id: str, user_id: str) -> Optional[DocumentChunking]:
        """Get chunking by document and user (for warning check)."""
        return self.db.query(DocumentChunking).filter(
            DocumentChunking.document_id == document_id,
            DocumentChunking.user_id == user_id
        ).first()

    def get_accessible_chunkings(self, user_id: str, load_relations: bool = False) -> list[type[DocumentChunking]]:
        """Get user's chunkings (own + public)."""
        query = self.db.query(DocumentChunking)
        if load_relations:
            query = query.options(
                joinedload(DocumentChunking.user),
                joinedload(DocumentChunking.document),
                joinedload(DocumentChunking.parsing_template)
            )

        return query.filter(
            or_(
                DocumentChunking.user_id == user_id,
                DocumentChunking.is_public == True
            )
        ).order_by(DocumentChunking.created_at.desc()).all()

    def get_with_chunk_count(self, user_id: str) -> List[Tuple[DocumentChunking, int, str, str, str]]:
        """Get chunkings with counts via single query (~50ms for 100 configs, 10K chunks)."""
        return self.db.query(
            DocumentChunking,
            func.count(DocumentChunk.id).label('chunk_count'),
            Document.file_name.label('document_name'),
            ParsingTemplate.template_name.label('template_name'),
            User.display_name.label('uploader_name')
        ).outerjoin(
            DocumentChunk,
            DocumentChunking.id == DocumentChunk.document_chunking_id
        ).join(
            Document,
            DocumentChunking.document_id == Document.id
        ).join(
            ParsingTemplate,
            DocumentChunking.template_id == ParsingTemplate.id
        ).join(
            User,
            DocumentChunking.user_id == User.id
        ).filter(
            or_(
                DocumentChunking.user_id == user_id,
                DocumentChunking.is_public == True
            )
        ).group_by(
            DocumentChunking.id,
            Document.file_name,
            ParsingTemplate.template_name,
            User.display_name
        ).order_by(
            DocumentChunking.created_at.desc()
        ).all()

    def update(self, doc_chunking: DocumentChunking) -> DocumentChunking:
        self.db.commit()
        self.db.refresh(doc_chunking)
        return doc_chunking

    def delete(self, doc_chunking: DocumentChunking) -> None:
        """Delete chunking (cascades to chunks)."""
        self.db.delete(doc_chunking)
        self.db.commit()
