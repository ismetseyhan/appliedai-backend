from pydantic import BaseModel, Field
from typing import List


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Research question")
    max_searches: int = Field(3, ge=1, le=5, description="Maximum number of web searches")


class ResearchReference(BaseModel):
    reference_id: str
    title: str
    url: str
    snippet: str


class AnswerWithCitations(BaseModel):
    """LLM structured output for answer synthesis with citations"""
    answer: str
    cited_reference_ids: List[str]


class AgentStep(BaseModel):
    step_number: int
    action: str
    action_input: str
    observation: str


class ResearchResponse(BaseModel):
    query: str
    final_answer: str
    references: List[ResearchReference]
    steps: List[AgentStep]
    execution_time_ms: int
