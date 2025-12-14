from fastapi import APIRouter, Depends, status
from app.api.deps import get_current_user, get_document_chunking_service
from app.entities.user import User
from app.schemas.document_chunking import (
    DocumentChunkingCreateRequest,
    DocumentChunkingUpdateRequest,
    DocumentChunkingResponse,
    DocumentChunkingCreateResponse,
    DocumentChunkingListResponse,
    CheckExistsResponse
)
from app.services.document_chunking_service import DocumentChunkingService


router = APIRouter()


@router.post(
    "",
    response_model=DocumentChunkingCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document chunking process."
)
async def create_document_chunking(
    request: DocumentChunkingCreateRequest,
    current_user: User = Depends(get_current_user),
    service: DocumentChunkingService = Depends(get_document_chunking_service)
):
    """
    Create a new document chunking process configuration.
    """
    return await service.create_document_chunking(request, current_user)


@router.get(
    "",
    response_model=DocumentChunkingListResponse,
    summary="List document chunking processes"
)
async def list_document_chunking(
    current_user: User = Depends(get_current_user),
    service: DocumentChunkingService = Depends(get_document_chunking_service)
):
    """
    List all document chunking processes accessible to the current user (private +public).
    """
    return service.list_document_chunking_processes(current_user)


@router.get(
    "/check-exists/{document_id}",
    response_model=CheckExistsResponse,
    summary="Check whether a chunking process exists for the document."
)
async def check_exists(
    document_id: str,
    current_user: User = Depends(get_current_user),
    service: DocumentChunkingService = Depends(get_document_chunking_service)
):
    """
    Check whether the current user already has a chunking process configured
    for the specified document.
    """
    return service.check_exists_for_document(document_id, current_user)


@router.get(
    "/{template_id}",
    response_model=DocumentChunkingResponse,
    summary="Get a document chunking process by ID"
)
async def get_document_chunking(
    template_id: str,
    current_user: User = Depends(get_current_user),
    service: DocumentChunkingService = Depends(get_document_chunking_service)
):
    """
    Retrieve document chunking process details by ID.
    """
    return service.get_by_id(template_id, current_user)


@router.put(
    "/{template_id}",
    response_model=DocumentChunkingResponse,
    summary="Update a document chunking process"
)
async def update_document_chunking(
    template_id: str,
    request: DocumentChunkingUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: DocumentChunkingService = Depends(get_document_chunking_service)
):
    """
    Update a document chunking process (owner only).
    """
    return service.update_document_chunking_detail(template_id, request, current_user)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document chunking process"
)
async def delete_document_chunking(
    template_id: str,
    current_user: User = Depends(get_current_user),
    service: DocumentChunkingService = Depends(get_document_chunking_service)
):
    """
    Delete a document chunking process (owner only).
    """
    service.delete_document_chunking_processes(template_id, current_user)
    return None
