from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List, Union
from datetime import datetime


class RecordStartConfig(BaseModel):
    pattern: str
    flags: List[str]


class FieldConfigV2(BaseModel):
    key: str
    labels: List[str]
    flags: List[str]
    type: str
    required: bool
    normalize_whitespace: bool = True
    split: Optional[str] = None
    item_strip: Optional[bool] = None


class CleanupConfig(BaseModel):
    drop_page_number_lines: Optional[bool] = False
    drop_lines_matching: Optional[List[str]] = []
    join_hyphenated_words: Optional[bool] = False
    collapse_whitespace: Optional[bool] = False
    replace: Optional[List[Dict[str, str]]] = []


class RecordConfig(BaseModel):
    split_strategy: str = "start_pattern"
    start: RecordStartConfig
    max_record_chars: Optional[int] = None


class OutputConfig(BaseModel):
    as_dict: bool = False
    id_field: str = "id"
    include_raw_record: bool = False
    skip_records_missing_required: bool = False


class TemplateJSONV2(BaseModel):
    template_version: int = 2
    pdf_text_cleanup: Optional[CleanupConfig] = None
    record: RecordConfig
    fields: List[FieldConfigV2]
    output: Optional[OutputConfig] = None


class TemplateCreateRequest(BaseModel):
    template_name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    doc_type: str = "record_list"
    template_json: Dict[str, Any]

    parsed_record_preview: Optional[List[Dict[str, Any]]] = Field(default=None, description="1-element list with sample record")
    metadata_keywords: Optional[List[str]] = Field(default=None, description="Metadata fields (optional)")
    llm_text: List[str] = Field(description="LLM context fields (required)")
    embedding_text: List[str] = Field(description="Embedding fields (required)")
    is_public: bool = False

    @field_validator('parsed_record_preview')
    @classmethod
    def validate_preview_structure(cls, v):
        if v is not None:
            if not isinstance(v, list) or len(v) != 1 or not isinstance(v[0], dict):
                raise ValueError("parsed_record_preview must be a 1-element list containing a dict")
        return v

    @field_validator('metadata_keywords', 'llm_text', 'embedding_text')
    @classmethod
    def validate_field_names(cls, v, info):
        if v:
            for field_name in v:
                if not isinstance(field_name, str) or not field_name.strip():
                    raise ValueError(f"{info.field_name} must contain non-empty strings")
        return v


class TemplateUpdateRequest(BaseModel):
    template_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    template_json: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None

    parsed_record_preview: Optional[List[Dict[str, Any]]] = None
    metadata_keywords: Optional[List[str]] = None
    llm_text: Optional[List[str]] = None
    embedding_text: Optional[List[str]] = None


class TemplateResponse(BaseModel):
    id: str
    user_id: str
    uploader_name: Optional[str] = None
    template_name: str
    description: Optional[str]
    doc_type: str
    template_json: Dict[str, Any]
    parsed_record_preview: Optional[List[Dict[str, Any]]] = None
    metadata_keywords: Optional[List[str]] = None
    llm_text: Optional[List[str]] = None
    embedding_text: Optional[List[str]] = None
    is_public: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]
    total: int


class GenerateTemplateRequest(BaseModel):
    document_id: str
    sample_pages: int = Field(1, ge=1, le=10)


class MinimalTemplateResponse(BaseModel):
    record_start: RecordStartConfig
    id_key: Optional[str]
    fields: List[FieldConfigV2]


class TemplateGenerationResponse(BaseModel):
    suggested_template: MinimalTemplateResponse
    full_template: Dict[str, Any]
    parsed_records: Union[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]


class TestParseRequest(BaseModel):
    document_id: str
    template_json: Dict[str, Any]
    sample_pages: int = Field(1, ge=1, le=10)


class TestParseResponse(BaseModel):
    success: bool
    parsed_records: Optional[Union[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # "json_error", "regex_error", "parse_error"
