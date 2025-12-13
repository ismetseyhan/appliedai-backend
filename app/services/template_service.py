from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.entities.template import Template
from app.entities.user import User
from app.schemas.template import (
    TemplateCreateRequest, TemplateUpdateRequest, TemplateResponse, TemplateListResponse,
    GenerateTemplateRequest, TemplateGenerationResponse,
    MinimalTemplateResponse, TestParseRequest, TestParseResponse
)
from app.repositories.template_repository import TemplateRepository
from app.repositories.document_repository import DocumentRepository
from app.services.firebase_storage_service import FirebaseStorageService
from app.services.pdf_extraction_service import PDFExtractionService
from app.services.template_parser_service import TemplateParserService
from app.services.llm_template_generator_service import LLMTemplateGeneratorService


class TemplateService:

    def __init__(
            self,
            db: Session,
            storage_service: FirebaseStorageService,
            llm_generator_service: LLMTemplateGeneratorService
    ):
        self.db = db
        self.storage_service = storage_service
        self.llm_generator = llm_generator_service
        self.template_repo = TemplateRepository(db)
        self.document_repo = DocumentRepository(db)
        self.pdf_extractor = PDFExtractionService()
        self.parser = TemplateParserService()

    async def generate_template_from_document(
            self,
            request: GenerateTemplateRequest,
            current_user: User
    ) -> TemplateGenerationResponse:
        document = self.document_repo.get_by_id(request.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if document.user_id != current_user.id and not document.is_public:
            raise HTTPException(status_code=403, detail="Access denied")

        pdf_bytes = self.storage_service.download_file(document.storage_path)
        if not pdf_bytes:
            raise HTTPException(status_code=500, detail="Failed to download document")


        sample_text = self.pdf_extractor.extract_text_from_bytes(
            pdf_bytes,
            max_pages=request.sample_pages
        )

        minimal_template_dict = await self.llm_generator.generate_minimal_template(sample_text)

        fields = minimal_template_dict["fields"]
        id_field = minimal_template_dict.get("id_key")

        if not id_field:
            preferred = ("id", "no", "number", "code")
            cand = next(
                (f["key"] for f in fields if any(p in f["key"].lower() for p in preferred)),
                None
            )
            id_field = cand or next((f["key"] for f in fields if f.get("required")), fields[0]["key"])

        sanitized_fields = []
        for f in fields:
            f2 = dict(f)
            f2.setdefault("normalize_whitespace", True)

            if f2.get("type") == "list":
                f2.setdefault("split", ",")
                f2.setdefault("item_strip", True)
            else:
                f2.pop("split", None)
                f2.pop("item_strip", None)

            sanitized_fields.append(f2)

        full_template_for_preview = {
            "pdf_text_cleanup": {
                "drop_page_number_lines": True,
                "join_hyphenated_words": True,
                "collapse_whitespace": True
            },
            "record": {
                "split_strategy": "start_pattern",
                "start": minimal_template_dict["record_start"],
                "max_record_chars": 30000
            },
            "fields": sanitized_fields,
            "output": {
                "as_dict": False,
                "id_field": id_field,
                "include_raw_record": True,
                "skip_records_missing_required": False
            }
        }

        parsed_result = self.parser.parse_pdf(sample_text, full_template_for_preview)

        # Check as_dict flag
        as_dict = full_template_for_preview.get("output", {}).get("as_dict", False)

        # Limit to 1 record for preview
        MAX_PREVIEW_RECORDS = 1

        if isinstance(parsed_result, dict):
            if as_dict:
                # Return as dict
                items = list(parsed_result.items())[:MAX_PREVIEW_RECORDS]
                parsed_records = dict(items)
            else:
                # Convert to list
                records_list = list(parsed_result.values())
                parsed_records = records_list[:MAX_PREVIEW_RECORDS]
        else:
            # Already a list
            parsed_records = parsed_result[:MAX_PREVIEW_RECORDS]

        minimal_template_dict["fields"] = sanitized_fields
        minimal_template_response = MinimalTemplateResponse(**minimal_template_dict)

        return TemplateGenerationResponse(
            suggested_template=minimal_template_response,
            full_template=full_template_for_preview,
            parsed_records=parsed_records
        )

    async def test_parse_template(
            self,
            request: TestParseRequest,
            current_user: User
    ) -> TestParseResponse:
        """
        Test parse a document with a custom template.
        """
        import re

        document = self.document_repo.get_by_id(request.document_id)
        if not document:
            return TestParseResponse(
                success=False,
                error="Document not found",
                error_type="document_error"
            )

        if document.user_id != current_user.id and not document.is_public:
            return TestParseResponse(
                success=False,
                error="Access denied to this document",
                error_type="permission_error"
            )

        try:
            pdf_bytes = self.storage_service.download_file(document.storage_path)
            if not pdf_bytes:
                return TestParseResponse(
                    success=False,
                    error="Failed to download document from storage",
                    error_type="storage_error"
                )

            sample_text = self.pdf_extractor.extract_text_from_bytes(
                pdf_bytes,
                max_pages=request.sample_pages
            )

            # Validate template structure
            template_json = request.template_json

            # Test regex compilation
            try:
                record_start = template_json.get("record", {}).get("start", {})
                pattern = record_start.get("pattern")
                if pattern:
                    flags = record_start.get("flags", [])
                    self.parser.compile_re(pattern, flags)

                # Test field patterns
                for field in template_json.get("fields", []):
                    for label in field.get("labels", []):
                        field_flags = field.get("flags", [])
                        self.parser.compile_re(label, field_flags)

            except re.error as e:
                return TestParseResponse(
                    success=False,
                    error=f"Invalid regex pattern: {str(e)}",
                    error_type="regex_error"
                )
            except Exception as e:
                return TestParseResponse(
                    success=False,
                    error=f"Template validation error: {str(e)}",
                    error_type="validation_error"
                )

            parsed_result = self.parser.parse_pdf(sample_text, template_json)

            # Check as_dict flag
            as_dict = template_json.get("output", {}).get("as_dict", False)

            # Limit to 1 record for preview
            MAX_PREVIEW_RECORDS = 1

            if isinstance(parsed_result, dict):
                if as_dict:
                    items = list(parsed_result.items())[:MAX_PREVIEW_RECORDS]
                    parsed_records = dict(items)
                else:
                    # Convert to list
                    records_list = list(parsed_result.values())
                    parsed_records = records_list[:MAX_PREVIEW_RECORDS]
            else:
                # Already a list
                parsed_records = parsed_result[:MAX_PREVIEW_RECORDS]

            if isinstance(parsed_records, dict):
                is_empty = len(parsed_records) == 0
            else:
                is_empty = len(parsed_records) == 0

            if is_empty:
                return TestParseResponse(
                    success=False,
                    error="No records found. Check if the record start pattern matches your document.",
                    error_type="parse_error"
                )

            return TestParseResponse(
                success=True,
                parsed_records=parsed_records
            )

        except Exception as e:
            return TestParseResponse(
                success=False,
                error=f"Parse error: {str(e)}",
                error_type="parse_error"
            )

    def create_template(
            self,
            request: TemplateCreateRequest,
            current_user: User
    ) -> TemplateResponse:
        existing = self.template_repo.get_by_user_and_name(
            current_user.id,
            request.template_name
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Template '{request.template_name}' already exists"
            )

        template = Template(
            user_id=current_user.id,
            template_name=request.template_name,
            description=request.description,
            doc_type=request.doc_type,
            template_json=request.template_json,
            parsed_record_preview=request.parsed_record_preview,
            metadata_keywords=request.metadata_keywords,
            llm_text=request.llm_text,
            embedding_text=request.embedding_text,
            is_public=request.is_public
        )

        template = self.template_repo.create(template)

        response = TemplateResponse.model_validate(template)
        response.uploader_name = current_user.display_name
        return response

    def list_templates(self, current_user: User) -> TemplateListResponse:
        templates = self.template_repo.get_accessible_templates(
            current_user.id,
            load_user=True
        )

        template_responses = []
        for tpl in templates:
            resp = TemplateResponse.model_validate(tpl)
            resp.uploader_name = tpl.user.display_name if tpl.user else None
            template_responses.append(resp)

        return TemplateListResponse(
            templates=template_responses,
            total=len(template_responses)
        )

    def get_by_id(self, template_id: str, current_user: User) -> TemplateResponse:
        template = self.template_repo.get_by_id(template_id, load_user=True)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if template.user_id != current_user.id and not template.is_public:
            raise HTTPException(status_code=403, detail="Access denied")

        response = TemplateResponse.model_validate(template)
        response.uploader_name = template.user.display_name if template.user else None
        return response

    def update_template(self, template_id: str, request: TemplateUpdateRequest, current_user: User) -> TemplateResponse:
        template = self.template_repo.get_by_id(template_id, load_user=True)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only the owner can edit this template")

        if request.template_name is not None:
            template.template_name = request.template_name
        if request.description is not None:
            template.description = request.description
        if request.template_json is not None:
            template.template_json = request.template_json
        if request.is_public is not None:
            template.is_public = request.is_public
        if request.parsed_record_preview is not None:
            template.parsed_record_preview = request.parsed_record_preview
        if request.metadata_keywords is not None:
            template.metadata_keywords = request.metadata_keywords
        if request.llm_text is not None:
            template.llm_text = request.llm_text
        if request.embedding_text is not None:
            template.embedding_text = request.embedding_text

        updated_template = self.template_repo.update(template)

        response = TemplateResponse.model_validate(updated_template)
        response.uploader_name = current_user.display_name
        return response

    def delete_template(self, template_id: str, current_user: User) -> None:
        template = self.template_repo.get_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only the owner can delete this template")

        self.template_repo.delete(template)
