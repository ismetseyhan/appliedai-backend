"""
Document API Endpoints - Thin controllers.
"""
from fastapi import APIRouter, Depends, status, UploadFile, File, Form

from app.api.deps import get_current_user, get_document_service
from app.entities.user import User
from app.schemas.document import (
    DocumentResponse,
    DocumentWithUrl,
    DocumentList,
    TogglePublicRequest
)
from app.services.document_service import DocumentService


router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload PDF document"
)
async def upload_document(
    file: UploadFile = File(...),
    is_public: bool = Form(False),
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service)
):
    """
    Upload a PDF document to Firebase Storage.

    - **file**: PDF file to upload
    - **is_public**: Make file publicly accessible (default: false)
    """
    return service.upload_document(
        file=file,
        user=current_user,
        is_public=is_public
    )


@router.get(
    "",
    response_model=DocumentList,
    summary="List user documents"
)
async def list_documents(
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service)
):
    """
    List all documents accessible to current user.

    Returns: User's own documents + all public documents
    """
    return service.list_accessible_documents(current_user=current_user)


@router.get(
    "/{document_id}",
    response_model=DocumentWithUrl,
    summary="Get document with signed URL"
)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service)
):
    """
    Get document details with signed download URL.

    - **document_id**: Document ID
    """
    return service.get_document_with_url(
        document_id=document_id,
        current_user=current_user,
        expiration_hours=1
    )


@router.patch(
    "/{document_id}/public",
    response_model=DocumentResponse,
    summary="Toggle document public status"
)
async def toggle_public_status(
    document_id: str,
    request: TogglePublicRequest,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service)
):
    """
    Change document public/private status.

    - **document_id**: Document ID
    - **is_public**: New public status
    """
    return service.toggle_public_status(
        document_id=document_id,
        current_user=current_user,
        is_public=request.is_public
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document"
)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service)
):
    """
    Delete document from both storage and database

    - **document_id**: Document ID
    """
    service.delete_document(
        document_id=document_id,
        current_user=current_user
    )
    return None
