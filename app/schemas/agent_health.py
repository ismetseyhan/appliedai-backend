"""
Agent Health Check Schemas
"""
from pydantic import BaseModel
from typing import Literal


class AgentHealthStatus(BaseModel):
    agent_name: str
    status: Literal["healthy", "not_configured", "no_database", "no_prompt", "no_active_processes"]
    message: str


class SystemHealthResponse(BaseModel):
    overall_status: Literal["healthy", "partial", "unhealthy"]
    research_agent: AgentHealthStatus
    text_to_sql_agent: AgentHealthStatus
    rag_agent: AgentHealthStatus
