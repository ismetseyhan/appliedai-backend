from pydantic import BaseModel


class AgentSettingsResponse(BaseModel):
    """Response schema for agent settings"""
    query_checker_enabled: bool


class QueryCheckerToggleRequest(BaseModel):
    """Request schema for toggling query checker"""
    enabled: bool
