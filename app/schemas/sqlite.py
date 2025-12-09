"""
SQLite Database Schemas - request/response models.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class SQLiteDatabaseMetadata(BaseModel):
    """PostgreSQL postgresql metadata"""
    id: str
    database_name: str
    file_size: int
    storage_path: str
    allowed_operations: List[str]
    sql_agent_prompt: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DatabaseInfoResponse(BaseModel):
    """Response schema for database info"""
    exists: bool
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    upload_date: Optional[datetime] = None
    metadata: Optional[SQLiteDatabaseMetadata] = None


class TableColumn(BaseModel):
    """Schema for a table column"""
    name: str
    type: str


class TableSchema(BaseModel):
    """Schema for a single table"""
    table_name: str
    columns: List[TableColumn]


class DatabaseSchema(BaseModel):
    """Full database schema"""
    tables: List[TableSchema]


class QueryRequest(BaseModel):
    """SQL query request"""
    query: str


class QueryResult(BaseModel):
    """SQL query result"""
    columns: List[str]
    rows: List[List[Any]]
    row_count: int


class TablePreviewResponse(BaseModel):
    """Table preview with sample data"""
    table_name: str
    columns: List[str]
    rows: List[List[Any]]
    total_rows: int
    preview_limit: int


class AllowedOperationsUpdate(BaseModel):
    """Request to update allowed operations"""
    allowed_operations: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "allowed_operations": ["SELECT", "INSERT", "UPDATE"]
            }
        }


# ============================================================================
#  Dynamic Agent Prompt Schemas
# ============================================================================

class PromptGenerationResponse(BaseModel):
    """Response for prompt generation"""
    prompt: str
    database_name: str
    generated_at: datetime


class PromptUpdateRequest(BaseModel):
    """Request to update prompt manually"""
    prompt: str

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "You are a SQL expert assistant..."
            }
        }

    def validate_prompt_length(self):
        if len(self.prompt.strip()) < 10:
            raise ValueError("Prompt must be at least 10 characters")
