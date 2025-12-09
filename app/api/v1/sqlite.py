"""
SQLite API Endpoints
"""
from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException, BackgroundTasks
from typing import Optional
from datetime import datetime

from app.api.deps import get_sqlite_service, get_llm_service, get_current_user
from app.schemas.sqlite import (
    DatabaseInfoResponse,
    DatabaseSchema,
    QueryRequest,
    QueryResult,
    TablePreviewResponse,
    AllowedOperationsUpdate,
    SQLiteDatabaseMetadata,
    PromptGenerationResponse,
    PromptUpdateRequest,
)
from app.services.sqlite_service import SQLiteService
from app.services.llm_service import LLMService
from app.entities.user import User


router = APIRouter()


@router.post(
    "/upload",
    response_model=DatabaseInfoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload SQLite database"
)
async def upload_database(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    service: SQLiteService = Depends(get_sqlite_service),
    llm_service: LLMService = Depends(get_llm_service)
):
    """Upload SQLite database and trigger background prompt generation"""
    db_info = service.upload_database(file=file)
    background_tasks.add_task(service.generate_sql_agent_prompt, llm_service)
    return db_info


@router.get(
    "/info",
    response_model=DatabaseInfoResponse,
    summary="Get database information"
)
async def get_database_info(
    service: SQLiteService = Depends(get_sqlite_service)
):
    """Get database information"""
    return service.get_database_info()


@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete database"
)
async def delete_database(
    service: SQLiteService = Depends(get_sqlite_service)
):
    """Delete database from storage"""
    service.delete_database()
    return None


@router.get(
    "/schema",
    response_model=DatabaseSchema,
    summary="Get database schema"
)
async def get_schema(
    service: SQLiteService = Depends(get_sqlite_service)
):
    """Get database schema"""
    return service.get_schema()


@router.post(
    "/query",
    response_model=QueryResult,
    summary="Execute SQL query"
)
async def execute_query(
    request: QueryRequest,
    service: SQLiteService = Depends(get_sqlite_service)
):
    """Execute SQL query with permission checks"""
    return service.execute_query(query=request.query)


@router.get(
    "/tables/{table_name}/preview",
    response_model=TablePreviewResponse,
    summary="Get table preview"
)
async def get_table_preview(
    table_name: str,
    limit: Optional[int] = 10,
    service: SQLiteService = Depends(get_sqlite_service)
):
    """Get sample rows from table"""
    return service.get_table_preview(table_name=table_name, limit=limit)


@router.patch(
    "/permissions",
    response_model=SQLiteDatabaseMetadata,
    summary="Update allowed operations"
)
async def update_permissions(
    request: AllowedOperationsUpdate,
    service: SQLiteService = Depends(get_sqlite_service)
):
    """Update allowed SQL operations"""
    return service.update_allowed_operations(allowed_operations=request.allowed_operations)


@router.post(
    "/generate-prompt",
    response_model=PromptGenerationResponse,
    summary="Generate Text-to-SQL agent prompt"
)
async def generate_agent_prompt(
    current_user: User = Depends(get_current_user),
    sqlite_service: SQLiteService = Depends(get_sqlite_service),
    llm_service: LLMService = Depends(get_llm_service)
):
    """Generate Text-to-SQL agent prompt using LLM"""
    try:
        prompt = await sqlite_service.generate_sql_agent_prompt(llm_service)
        db_record = sqlite_service.db_repository.get_current_database()
        if not db_record:
            raise HTTPException(status_code=404, detail="No database uploaded")
        return PromptGenerationResponse(
            prompt=prompt,
            database_name=db_record.database_name,
            generated_at=datetime.utcnow()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prompt generation failed: {str(e)}")


@router.get(
    "/agent-prompt",
    response_model=PromptGenerationResponse,
    summary="Get current Text-to-SQL agent prompt"
)
async def get_agent_prompt(
    current_user: User = Depends(get_current_user),
    sqlite_service: SQLiteService = Depends(get_sqlite_service)
):
    """Get current Text-to-SQL agent prompt"""
    try:
        db_record = sqlite_service.db_repository.get_current_database()
        if not db_record:
            raise HTTPException(status_code=404, detail="No database uploaded")
        if not db_record.sql_agent_prompt:
            raise HTTPException(status_code=404, detail="Prompt not generated yet")
        return PromptGenerationResponse(
            prompt=db_record.sql_agent_prompt,
            database_name=db_record.database_name,
            generated_at=db_record.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/agent-prompt",
    response_model=PromptGenerationResponse,
    summary="Update Text-to-SQL agent prompt"
)
async def update_agent_prompt(
    request: PromptUpdateRequest,
    current_user: User = Depends(get_current_user),
    sqlite_service: SQLiteService = Depends(get_sqlite_service)
):
    """Update Text-to-SQL agent prompt with user edits"""
    try:
        db_record = sqlite_service.db_repository.get_current_database()
        if not db_record:
            raise HTTPException(status_code=404, detail="No database uploaded")
        updated_record = sqlite_service.db_repository.update_sql_agent_prompt(
            db_id=db_record.id,
            prompt=request.prompt
        )
        return PromptGenerationResponse(
            prompt=updated_record.sql_agent_prompt,
            database_name=updated_record.database_name,
            generated_at=updated_record.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
