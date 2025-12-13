from typing import List, Optional
from app.services.llm_service import LLMService
from app.prompts.prompt_manager import TEMPLATE_GENERATION_PROMPT
from pydantic import BaseModel


class FieldMappingConfig(BaseModel):
    key: str
    labels: List[str]
    flags: List[str]
    type: str
    required: bool
    normalize_whitespace: bool = True
    split: Optional[str] = None
    item_strip: Optional[bool] = None

    class Config:
        extra = "forbid"


class RecordStartConfig(BaseModel):
    pattern: str
    flags: List[str]

    class Config:
        extra = "forbid"


class LLMTemplateGeneratorOutput(BaseModel):
    record_start: RecordStartConfig
    id_key: Optional[str]
    fields: List[FieldMappingConfig]

    class Config:
        extra = "forbid"


class LLMTemplateGeneratorService:

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def generate_minimal_template(self, sample_text: str) -> dict:
        prompt = TEMPLATE_GENERATION_PROMPT.format(sample_text=sample_text[:2500])

        llm_with_structure = self.llm_service.get_structured_llm(LLMTemplateGeneratorOutput)
        response = await llm_with_structure.ainvoke(prompt)

        return response.model_dump()
