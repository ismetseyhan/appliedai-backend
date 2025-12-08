"""
SQLite API Endpoints -
"""
from fastapi import APIRouter, Depends, status, UploadFile, File
from typing import Optional

from app.api.deps import get_sqlite_service
from app.schemas.sqlite import (
    DatabaseInfoResponse,
    DatabaseSchema,
    QueryRequest,
    QueryResult,
    TablePreviewResponse,
    AllowedOperationsUpdate,
    SQLiteDatabaseMetadata
)
from app.services.sqlite_service import SQLiteService


router = APIRouter()


@router.post(
    "/upload",
    response_model=DatabaseInfoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload SQLite database"
)
async def upload_database(
    file: UploadFile = File(...),
    service: SQLiteService = Depends(get_sqlite_service)
):
    """
    Upload a SQLite .db file to Firebase Storage (global).

    Replaces existing database if any.

    - **file**: SQLite .db file to upload
    """
    return service.upload_database(file=file)


@router.get(
    "/info",
    response_model=DatabaseInfoResponse,
    summary="Get database information"
)
async def get_database_info(
    service: SQLiteService = Depends(get_sqlite_service)
):
    """
    Get information about current global database.

    Returns:
    - exists: Whether database exists
    - file_name: Database filename
    - file_size: Size in bytes
    - upload_date: Last upload timestamp
    """
    return service.get_database_info()


@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete database"
)
async def delete_database(
    service: SQLiteService = Depends(get_sqlite_service)
):
    """
    Delete global SQLite database from Firebase Storage.
    """
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
    """
    Get schema of global SQLite database.

    Returns tables with their columns and data types.
    """
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
    """
    Execute a read-only SQL query on global database.

    Security:
    - Only SELECT queries allowed
    - SQL injection prevention
    - No DDL/DML operations

    - **query**: SQL SELECT statement
    """
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
    """
    Get sample rows from a table.

    - **table_name**: Name of the table
    - **limit**: Number of rows to return (default: 10)
    """
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
    """
    Update allowed SQL operations for the current database.

    - **allowed_operations**: List of allowed operations (SELECT, INSERT, UPDATE, DELETE)
    """
    return service.update_allowed_operations(allowed_operations=request.allowed_operations)
