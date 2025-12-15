"""
SQLite Service -  SQLite database management.

Handles:
- Upload .db files to Firebase Storage (global path: sqlite/current.db)
- Download .db files to LOCAL CACHE for querying
- Extract schema information
- Sample data retrieval
"""
import re
import sqlite3
from pathlib import Path
from typing import Optional, List
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session

from app.services.firebase_storage_service import FirebaseStorageService
from app.services.prompt_generator_service import PromptGeneratorService
from app.repositories.sqlite_database_repository import SQLiteDatabaseRepository
from app.schemas.sqlite import (
    DatabaseInfoResponse,
    DatabaseSchema,
    TableSchema,
    TableColumn,
    QueryResult,
    TablePreviewResponse,
    SQLiteDatabaseMetadata
)


class SQLiteService:
    GLOBAL_DB_PATH = "sqlite/current.db"
    CACHE_DIR = Path(__file__).parent.parent / ".cache" / "sqlite"  # Local cache directory
    CACHE_FILE = CACHE_DIR / "current.db"  # Cached database file

    def __init__(self, storage_service: FirebaseStorageService, db: Session):
        self.storage_service = storage_service
        self.db_repository = SQLiteDatabaseRepository(db)
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _download_to_cache(self) -> Path:
        """Download database from Firebase to local cache."""
        blob = self.storage_service.bucket.blob(self.GLOBAL_DB_PATH)

        if not blob.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database file not found in storage"
            )

        file_content = blob.download_as_bytes()
        self.CACHE_FILE.write_bytes(file_content)

        return self.CACHE_FILE

    def _invalidate_cache(self):
        """Delete cached database file to force re-download."""
        if self.CACHE_FILE.exists():
            self.CACHE_FILE.unlink()

    def upload_database(self, file: UploadFile) -> DatabaseInfoResponse:
        """Upload SQLite database to Firebase Storage and create metadata record."""

        if not file.filename.endswith('.db'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .db SQLite files are supported"
            )

        file_content = file.file.read()
        file_size = len(file_content)

        if not self._is_valid_sqlite(file_content):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid SQLite database file"
            )

        storage_path = self.storage_service.upload_file(
            file_content=file_content,
            user_id="",  # global not user based
            filename="current.db",
            folder="sqlite",
            content_type="application/x-sqlite3"
        )

        if not storage_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to storage"
            )

        self._invalidate_cache()

        db_record = self.db_repository.create_or_replace(
            database_name=file.filename,
            file_size=file_size,
            storage_path=self.GLOBAL_DB_PATH,
            allowed_operations=["SELECT", "INSERT", "UPDATE", "DELETE"]  # Default
        )

        blob = self.storage_service.bucket.blob(self.GLOBAL_DB_PATH)
        blob.reload()

        return DatabaseInfoResponse(
            exists=True,
            file_name=db_record.database_name,
            file_size=db_record.file_size,
            upload_date=blob.updated,
            metadata=SQLiteDatabaseMetadata.model_validate(db_record)
        )

    def get_database_info(self) -> DatabaseInfoResponse:
        """Get current database info and metadata."""
        blob = self.storage_service.bucket.blob(self.GLOBAL_DB_PATH)

        if not blob.exists():
            return DatabaseInfoResponse(exists=False)

        db_record = self.db_repository.get_current_database()

        blob.reload()
        return DatabaseInfoResponse(
            exists=True,
            file_name=db_record.database_name if db_record else "current.db",
            file_size=blob.size,
            upload_date=blob.updated,
            metadata=SQLiteDatabaseMetadata.model_validate(db_record) if db_record else None
        )

    def delete_database(self) -> None:
        """Delete database from Firebase Storage, PostgreSQL, and invalidate cache."""
        deleted = self.storage_service.delete_file(self.GLOBAL_DB_PATH)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database not found or already deleted"
            )

        self.db_repository.delete_by_storage_path(self.GLOBAL_DB_PATH)

        self._invalidate_cache()

    def get_schema(self) -> DatabaseSchema:
        """Get database schema (tables, columns, data types)."""

        blob = self.storage_service.bucket.blob(self.GLOBAL_DB_PATH)
        if not blob.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No database found. Please upload a database first."
            )

        with self._get_sqlite_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = cursor.fetchall()

            table_schemas = []
            for (table_name,) in tables:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                column_list = [
                    TableColumn(name=col[1], type=col[2])
                    for col in columns
                ]

                table_schemas.append(
                    TableSchema(
                        table_name=table_name,
                        columns=column_list
                    )
                )

            return DatabaseSchema(tables=table_schemas)

    def update_allowed_operations(self, allowed_operations: List[str]) -> SQLiteDatabaseMetadata:
        """Update allowed SQL operations (SELECT, INSERT, UPDATE, DELETE)."""

        valid_operations = {"SELECT", "INSERT", "UPDATE", "DELETE"}
        if not all(op in valid_operations for op in allowed_operations):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid operations. Must be one of: {valid_operations}"
            )

        db_record = self.db_repository.get_current_database()
        if not db_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No database found. Please upload a database first."
            )

        updated_record = self.db_repository.update_allowed_operations(
            db_id=db_record.id,
            allowed_operations=allowed_operations
        )

        return SQLiteDatabaseMetadata.model_validate(updated_record)

    def execute_query(self, query: str) -> QueryResult:
        """Execute SQL query with permission and safety validation."""

        blob = self.storage_service.bucket.blob(self.GLOBAL_DB_PATH)
        if not blob.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No database found. Please upload a database first."
            )

        db_record = self.db_repository.get_current_database()
        allowed_operations = db_record.allowed_operations if db_record else ["SELECT"]

        query = ' '.join(query.split())

        if not self._is_safe_query(query, allowed_operations):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Query not allowed. Permitted operations: {', '.join(allowed_operations)}"
            )

        with self._get_sqlite_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute(query)

                query_upper = query.strip().upper()
                if query_upper.startswith(('INSERT', 'UPDATE', 'DELETE')):
                    conn.commit()
                    affected_rows = cursor.rowcount

                    modified_db_content = self.CACHE_FILE.read_bytes()
                    self.storage_service.upload_file(
                        file_content=modified_db_content,
                        user_id="",
                        filename="current.db",
                        folder="sqlite",
                        content_type="application/x-sqlite3"
                    )

                    return QueryResult(
                        columns=['affected_rows'],
                        rows=[[affected_rows]],
                        row_count=affected_rows
                    )
                else:
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    return QueryResult(
                        columns=columns,
                        rows=rows,
                        row_count=len(rows)
                    )
            except sqlite3.Error as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"SQL error: {str(e)}"
                )

    def get_table_preview(self, table_name: str, limit: int = 10) -> TablePreviewResponse:
        """Get sample rows from a table."""

        blob = self.storage_service.bucket.blob(self.GLOBAL_DB_PATH)
        if not blob.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No database found. Please upload a database first."
            )

        if not self._is_valid_table_name(table_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid table name"
            )

        with self._get_sqlite_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if not cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Table '{table_name}' not found"
                    )

                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                total_rows = cursor.fetchone()[0]

                cursor.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
                rows = cursor.fetchall()

                columns = [desc[0] for desc in cursor.description]

                return TablePreviewResponse(
                    table_name=table_name,
                    columns=columns,
                    rows=rows,
                    total_rows=total_rows,
                    preview_limit=limit
                )
            except sqlite3.Error as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database error: {str(e)}"
                )

    # ========== HELPER METHODS ==========

    def _get_sqlite_connection(self):
        """Context manager for SQLite connection. Downloads from Firebase if cache missing."""

        class SQLiteContextManager:
            def __init__(self, service: 'SQLiteService'):
                self.service = service
                self.connection = None

            def __enter__(self):

                if not self.service.CACHE_FILE.exists():
                    cache_path = self.service._download_to_cache()
                else:
                    cache_path = self.service.CACHE_FILE


                self.connection = sqlite3.connect(str(cache_path))
                return self.connection

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.connection:
                    self.connection.close()

        return SQLiteContextManager(self)

    def _is_valid_sqlite(self, file_content: bytes) -> bool:
        """Check if file is a valid SQLite database."""
        return file_content[:16] == b'SQLite format 3\x00'

    def _is_safe_query(self, query: str, allowed_operations: List[str]) -> bool:
        """Validate query permissions and block dangerous SQL (DDL, multi-statements, comments)."""
        cleaned = query.strip().upper()

        query_type = None
        if cleaned.startswith('SELECT'):
            query_type = 'SELECT'
        elif cleaned.startswith('INSERT'):
            query_type = 'INSERT'
        elif cleaned.startswith('UPDATE'):
            query_type = 'UPDATE'
        elif cleaned.startswith('DELETE'):
            query_type = 'DELETE'
        else:
            return False

        if query_type not in allowed_operations:
            return False

        always_blocked = ['DROP', 'ALTER', 'CREATE', 'EXEC', 'EXECUTE', 'ATTACH', 'DETACH']
        for keyword in always_blocked:
            if keyword in cleaned:
                return False

        if ';' in query[:-1]:
            return False

        if '--' in query or '/*' in query:
            return False

        return True

    def _is_valid_table_name(self, table_name: str) -> bool:
        """Validate table name to prevent SQL injection."""
        return bool(re.match(r'^[a-zA-Z0-9_]+$', table_name))

    def get_cached_db_path(self) -> str:
        """Get absolute path to cached database file. Downloads if not cached."""
        db_record = self.db_repository.get_current_database()
        if not db_record:
            raise ValueError("No database uploaded")

        if not self.CACHE_FILE.exists():
            self._download_to_cache()

        return str(self.CACHE_FILE.absolute())

    def get_current_database_metadata(self):
        """Get current database metadata record."""
        return self.db_repository.get_current_database()

    def update_agent_prompt(self, prompt: str) -> None:
        """Update SQL agent prompt for current database."""
        db_record = self.db_repository.get_current_database()
        if not db_record:
            raise ValueError("No database uploaded")

        self.db_repository.update_sql_agent_prompt(
            db_id=db_record.id,
            prompt=prompt
        )

    async def generate_sql_agent_prompt(self, llm_service) -> str:
        """Generate Text-to-SQL agent prompt using LLM and save to database."""
        db_record = self.db_repository.get_current_database()
        if not db_record:
            raise ValueError("No database uploaded")

        db_path = self.CACHE_FILE
        if not db_path.exists():
            self._download_to_cache()

        prompt_generator = PromptGeneratorService(llm_service)
        generated_prompt = await prompt_generator.generate_prompt(
            db_path=db_path,
            db_name=db_record.database_name,
            allowed_operations=db_record.allowed_operations
        )

        self.db_repository.update_sql_agent_prompt(
            db_id=db_record.id,
            prompt=generated_prompt
        )

        return generated_prompt
