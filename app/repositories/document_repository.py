"""
Document Repository - Database operations only.

This module handles all database operations for documents.
"""
from typing import List, Optional, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.entities.document import Document, ProcessingStatus


class DocumentRepository:
    """Repository for Document database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, document: Document) -> Document:
        """Create a new document record."""
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_by_id(self, document_id: str, load_user: bool = False) -> Optional[Document]:
        """Get document by ID."""
        query = self.db.query(Document)
        if load_user:
            query = query.options(joinedload(Document.user))
        return query.filter(Document.id == document_id).first()

    def get_by_storage_path(self, storage_path: str) -> Optional[Document]:
        """Get document by storage path."""
        return self.db.query(Document).filter(
            Document.storage_path == storage_path
        ).first()

    def get_accessible_documents(
        self,
        user_id: str,
        load_user: bool = False
    ) -> List[Document]:
        """
        Get all documents accessible to a user.
        Returns user's own documents + all public documents.
        """
        query = self.db.query(Document)
        if load_user:
            query = query.options(joinedload(Document.user))

        return query.filter(
            or_(
                Document.user_id == user_id,
                Document.is_public == True
            )
        ).order_by(Document.created_at.desc()).all()

    def update(self, document: Document) -> Document:
        """Update a document record."""
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document: Document) -> None:
        """Delete a document record."""
        self.db.delete(document)
        self.db.commit()

    def get_by_user_id(self, user_id: str) -> List[Document]:
        """Get all documents owned by a user."""
        return self.db.query(Document).filter(
            Document.user_id == user_id
        ).order_by(Document.created_at.desc()).all()

    def get_public_documents(self) -> List[Document]:
        """Get all public documents."""
        return self.db.query(Document).filter(
            Document.is_public == True
        ).order_by(Document.created_at.desc()).all()

    def update_processing_status(
        self,
        document_id: str,
        status: ProcessingStatus
    ) -> Optional[Document]:
        """Update document processing status."""
        document = self.get_by_id(document_id)
        if document:
            document.processing_status = status
            return self.update(document)
        return None
