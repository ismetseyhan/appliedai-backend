from fastapi import APIRouter, Depends, status
from app.api.deps import get_current_user, get_template_service
from app.entities.user import User
from app.schemas.parsing_template import (
    TemplateCreateRequest, TemplateUpdateRequest, TemplateResponse, TemplateListResponse,
    GenerateTemplateRequest, TemplateGenerationResponse,
    TestParseRequest, TestParseResponse
)
from app.services.template_service import TemplateService

router = APIRouter()


@router.post(
    "/generate",
    response_model=TemplateGenerationResponse,
    summary="Generate template from document sample"
)
async def generate_template(
    request: GenerateTemplateRequest,
    current_user: User = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service)
):
    return await service.generate_template_from_document(request, current_user)


@router.post(
    "/test-parse",
    response_model=TestParseResponse,
    summary="Test parse document with custom template"
)
async def test_parse(
    request: TestParseRequest,
    current_user: User = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service)
):
    """
    Test parsing a document with a custom template.
    Allows users to iteratively test and refine their templates.
    """
    return await service.test_parse_template(request, current_user)


@router.post(
    "/",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create template"
)
async def create_template(
    request: TemplateCreateRequest,
    current_user: User = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service)
):
    return service.create_template(request, current_user)


@router.get(
    "/",
    response_model=TemplateListResponse,
    summary="List templates"
)
async def list_templates(
    current_user: User = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service)
):
    return service.list_templates(current_user)


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Get template by ID"
)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service)
):
    return service.get_by_id(template_id, current_user)


@router.put(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Update template"
)
async def update_template(
    template_id: str,
    request: TemplateUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service)
):
    return service.update_template(template_id, request, current_user)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete template"
)
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service)
):
    service.delete_template(template_id, current_user)
