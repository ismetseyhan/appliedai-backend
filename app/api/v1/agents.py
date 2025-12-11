"""
AI Agents API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
import time

from app.api.deps import get_sqlite_service, get_llm_service, get_current_user, get_user_preferences_service, get_google_search_service
from app.schemas.text_to_sql import TextToSQLRequest, TextToSQLResponse
from app.schemas.research import ResearchRequest, ResearchResponse
from app.schemas.agent_settings import AgentSettingsResponse, QueryCheckerToggleRequest
from app.services.sqlite_service import SQLiteService
from app.services.llm_service import LLMService
from app.services.google_search_service import GoogleSearchService
from app.services.user_preferences_service import UserPreferencesService
from app.agents.text_to_sql_agent import TextToSQLAgent
from app.agents.research_agent import ResearchAgent
from app.entities.user import User


router = APIRouter()


@router.post(
    "/text-to-sql",
    response_model=TextToSQLResponse,
    summary="Convert natural language to SQL and execute"
)
async def text_to_sql(
    request: TextToSQLRequest,
    current_user: User = Depends(get_current_user),
    sqlite_service: SQLiteService = Depends(get_sqlite_service),
    llm_service: LLMService = Depends(get_llm_service),
    preferences_service: UserPreferencesService = Depends(get_user_preferences_service)
):
    """
    Convert natural language query to SQL using LangChain agent.
    Executes queries safely and returns results with reasoning steps.
    """
    start = time.time()

    try:
        agent = TextToSQLAgent(
            sqlite_service,
            llm_service,
            preferences_service,
            current_user.id
        )
        response = await agent.query(request.query, request.max_sql_queries)
        response.execution_time_ms = int((time.time() - start) * 1000)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text-to-SQL agent failed: {str(e)}")


@router.post(
    "/research",
    response_model=ResearchResponse,
    summary="Research questions using web search"
)
async def research(
    request: ResearchRequest,
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
    search_service: GoogleSearchService = Depends(get_google_search_service)
):
    """
    Research questions using Google Custom Search API.
    Performs multiple web searches and synthesizes answers with references.
    """
    start = time.time()

    try:
        agent = ResearchAgent(llm_service, search_service, current_user.id)
        response = await agent.query(request.query, request.max_searches)
        response.execution_time_ms = int((time.time() - start) * 1000)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research agent failed: {str(e)}")


@router.get(
    "/settings",
    response_model=AgentSettingsResponse,
    summary="Get user's Text-to-SQL agent settings"
)
async def get_agent_settings(
    current_user: User = Depends(get_current_user),
    preferences_service: UserPreferencesService = Depends(get_user_preferences_service)
):
    """Get user's agent configuration settings."""
    prefs_dict = preferences_service.get_all_preferences(current_user.id)
    return AgentSettingsResponse(
        query_checker_enabled=prefs_dict[UserPreferencesService.QUERY_CHECKER_ENABLED].lower() == "true"
    )


@router.patch(
    "/settings/query-checker",
    response_model=AgentSettingsResponse,
    summary="Toggle query checker feature"
)
async def toggle_query_checker(
    request: QueryCheckerToggleRequest,
    current_user: User = Depends(get_current_user),
    preferences_service: UserPreferencesService = Depends(get_user_preferences_service)
):
    """Enable or disable query checker validation."""
    preferences_service.set_query_checker_enabled(current_user.id, request.enabled)
    prefs_dict = preferences_service.get_all_preferences(current_user.id)
    return AgentSettingsResponse(
        query_checker_enabled=prefs_dict[UserPreferencesService.QUERY_CHECKER_ENABLED].lower() == "true"
    )
