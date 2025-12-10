"""
AI Agents API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
import time

from app.api.deps import get_sqlite_service, get_llm_service, get_current_user
from app.schemas.text_to_sql import TextToSQLRequest, TextToSQLResponse
from app.services.sqlite_service import SQLiteService
from app.services.llm_service import LLMService
from app.agents.text_to_sql_agent import TextToSQLAgent
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
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    Convert natural language query to SQL using LangChain agent.
    Executes queries safely and returns results with reasoning steps.
    """
    start = time.time()

    try:
        agent = TextToSQLAgent(sqlite_service, llm_service)
        response = await agent.query(request.query, request.max_sql_queries)
        response.execution_time_ms = int((time.time() - start) * 1000)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text-to-SQL agent failed: {str(e)}")
