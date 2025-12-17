"""
Document Service - Business logic layer.
"""
from typing import Optional, List
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session

from app.entities.document import Document, ProcessingStatus
from app.entities.user import User
from app.repositories.document_repository import DocumentRepository
from app.services.firebase_storage_service import FirebaseStorageService
from app.schemas.document import DocumentResponse, DocumentWithUrl, DocumentList


class DocumentService:
    """Service for document business logic."""

    def __init__(
        self,
        db: Session,
        storage_service: FirebaseStorageService
    ):
        self.storage_service = storage_service
        self.repository = DocumentRepository(db)

    def upload_document(
        self,
        file: UploadFile,
        user: User,
        is_public: bool = False
    ) -> DocumentResponse:
        """
        Upload a PDF document.

        Business logic:
        - Validate file type
        - Upload to storage
        - Create database record
        - Return response with uploader name
        """
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported"
            )

        if file.content_type != 'application/pdf':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Must be application/pdf"
            )

        # Read file content
        file_content = file.file.read()
        file_size = len(file_content)

        # Upload to Firebase Storage
        storage_path = self.storage_service.upload_file(
            file_content=file_content,
            user_id=user.id,
            filename=file.filename
        )

        if not storage_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to storage"
            )

        existing_document = self.repository.get_by_storage_path(storage_path)

        if existing_document:
            existing_document.file_size = file_size
            existing_document.processing_status = ProcessingStatus.PENDING
            document = self.repository.update(existing_document)
        else:
            document = Document(
                user_id=user.id,
                file_name=file.filename,
                file_path=f"documents/{user.id}/{file.filename}",
                storage_path=storage_path,
                file_size=file_size,
                mime_type='application/pdf',
                is_public=is_public,
                processing_status=ProcessingStatus.PENDING
            )
            document = self.repository.create(document)

        # Build response with uploader name
        response = DocumentResponse.model_validate(document)
        response.uploader_name = user.display_name
        return response

    def list_accessible_documents(
        self,
        current_user: User
    ) -> DocumentList:
        """
        List all documents accessible to current user.

        Business logic:
        - Get user's own documents + all public documents
        - Include uploader names
        """
        documents = self.repository.get_accessible_documents(
            user_id=current_user.id,
            load_user=True
        )

        # Build response with uploader names
        document_responses = []
        for doc in documents:
            doc_response = DocumentResponse.model_validate(doc)
            doc_response.uploader_name = doc.user.display_name if doc.user else None
            document_responses.append(doc_response)

        return DocumentList(
            documents=document_responses,
            total=len(document_responses)
        )

    def get_document_with_url(
        self,
        document_id: str,
        current_user: User,
        expiration_hours: int = 1
    ) -> DocumentWithUrl:
        """
        Get document details with signed download URL.

        Business logic:
        - Verify document exists
        - Check access permission
        - Generate signed URL
        - Return response with uploader name
        """
        document = self.repository.get_by_id(document_id, load_user=True)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Check access permission
        if document.user_id != current_user.id and not document.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Generate signed URL
        download_url = self.storage_service.get_download_url(
            storage_path=document.storage_path,
            expiration_hours=expiration_hours
        )

        if not download_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate download URL"
            )

        # Build response
        doc_dict = {
            **document.__dict__,
            "download_url": download_url,
            "uploader_name": document.user.display_name if document.user else None
        }
        return DocumentWithUrl(**doc_dict)

    def toggle_public_status(
        self,
        document_id: str,
        current_user: User,
        is_public: bool
    ) -> DocumentResponse:
        """
        Toggle document public/private status.

        Business logic:
        - Verify document exists
        - Verify user is owner
        - Update status
        """
        document = self.repository.get_by_id(document_id, load_user=True)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Only owner can change  status
        if document.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only document owner can change public status"
            )

        document.is_public = is_public
        document = self.repository.update(document)

        # Build response
        response = DocumentResponse.model_validate(document)
        response.uploader_name = document.user.display_name if document.user else None
        return response

    def delete_document(
        self,
        document_id: str,
        current_user: User
    ) -> None:
        """
        Delete document from both storage and database.

        Business logic:
        - Verify document exists
        - Verify user is owner
        - Delete from storage first
        - Delete from database
        """
        document = self.repository.get_by_id(document_id)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Only owner can delete
        if document.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only document owner can delete"
            )

        # Delete from Firebase Storage
        storage_deleted = self.storage_service.delete_file(document.storage_path)

        if not storage_deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete file from storage"
            )

        # Delete from database
        self.repository.delete(document)
