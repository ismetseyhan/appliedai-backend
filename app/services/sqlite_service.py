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

from app.services.firebase_storage import FirebaseStorageService
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

    def __init__(self, storage_service: FirebaseStorageService, db_repository: SQLiteDatabaseRepository):
        self.storage_service = storage_service
        self.db_repository = db_repository
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _download_to_cache(self) -> Path:
        """
        Download database from Firebase to local cache.
        Only called when cache is missing or invalidated.

        Returns:
            Path to cached database file
        """
        blob = self.storage_service.bucket.blob(self.GLOBAL_DB_PATH)

        if not blob.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database file not found in storage"
            )

        # Download to cache
        file_content = blob.download_as_bytes()
        self.CACHE_FILE.write_bytes(file_content)

        return self.CACHE_FILE

    def _invalidate_cache(self):
        """Delete cached database file to force re-download."""
        if self.CACHE_FILE.exists():
            self.CACHE_FILE.unlink()

    def upload_database(self, file: UploadFile) -> DatabaseInfoResponse:
        """
        Upload a SQLite .db file to Firebase Storage (global).

        Business logic:
        - Validate file extension (.db)
        - Validate SQLite magic bytes
        - Upload to Firebase Storage at fixed path: sqlite/current.db
        - Overwrites existing file if present
        """

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
        """
        Get information about current sqllite  database including metadata.

        Returns:
            exists: bool - whether database exists
            file_name: str - original uploaded filename
            file_size: int - size in bytes
            upload_date: datetime - last upload time
            metadata: database permissions and config
        """
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
        """
        Delete global SQLite database from Firebase Storage and invalidate cache.

        Business logic:
        - Delete from Firebase Storage at fixed path
        - Delete metadata record from PostgreSQL
        - Invalidate local cache
        """
        deleted = self.storage_service.delete_file(self.GLOBAL_DB_PATH)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database not found or already deleted"
            )

        self.db_repository.delete_by_storage_path(self.GLOBAL_DB_PATH)

        self._invalidate_cache()

    def get_schema(self) -> DatabaseSchema:
        """
        Get schema of global SQLite database.

        Returns tables with their columns and data types.
        """

        blob = self.storage_service.bucket.blob(self.GLOBAL_DB_PATH)
        if not blob.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No database found. Please upload a database first."
            )

        with self._get_sqlite_connection() as conn:
            cursor = conn.cursor()

            # Get all tables
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = cursor.fetchall()

            table_schemas = []
            for (table_name,) in tables:
                # Get column info for each table
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
        """
        Update allowed SQL operations for the current database.

        Args:
            allowed_operations: List of allowed operations (SELECT, INSERT, UPDATE, DELETE)

        Returns:
            Updated database metadata
        """

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
        """
        Execute SQL query on global database with permission checks.

        Reason :Security:
        - Validates query against allowed operations
        - SQL injection prevention via validation
        - Permission-based query execution
        """

        blob = self.storage_service.bucket.blob(self.GLOBAL_DB_PATH)
        if not blob.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No database found. Please upload a database first."
            )

        db_record = self.db_repository.get_current_database()
        allowed_operations = db_record.allowed_operations if db_record else ["SELECT"]

        #normalize newlines
        query = ' '.join(query.split())

        # Validate query safety and permissions
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

                    # Upload modified database -syncs with Cloud
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
                    # For SELECT, fetch results
                    rows = cursor.fetchall()
                    # Get column names
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
        """
        Get sample rows from a table.

        Args:
            table_name: Name of the table
            limit: Number of rows to return (default 10)
        """

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

                # Get column names
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
        """
        Get SQLite connection using cached file.

        Context manager that:
        1. Checks if cache exists
        2. If NO → Download from Firebase to cache
        3. If YES → Use cached file
        4. Opens connection to cached file (NO temp file!)
        5. Closes connection after use (cache file persists)
        """

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
                # Just close connection, DO NOT delete cache file
                if self.connection:
                    self.connection.close()

        return SQLiteContextManager(self)

    def _is_valid_sqlite(self, file_content: bytes) -> bool:
        """Check if file is a valid SQLite database."""
        # SQLite files start with "SQLite format 3\x00"
        return file_content[:16] == b'SQLite format 3\x00'

    def _is_safe_query(self, query: str, allowed_operations: List[str]) -> bool:
        """
        Validate query safety and permissions.

        Args:
            query: SQL query to validate
            allowed_operations: List of permitted operations (SELECT, INSERT, UPDATE, DELETE)

        Blocks:
        - Operations not in allowed_operations
        - DROP, ALTER, CREATE, EXEC, ATTACH, DETACH (always blocked)
        - Multiple statements (;)
        - Comments (-- or /* */)
        """
        # Remove whitespace and convert to uppercase
        cleaned = query.strip().upper()

        # Determine query type
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
            return False  # Unknown query type

        # Check if operation is allowed
        if query_type not in allowed_operations:
            return False

        # Always block  DDL keywords
        always_blocked = ['DROP', 'ALTER', 'CREATE', 'EXEC', 'EXECUTE', 'ATTACH', 'DETACH']
        for keyword in always_blocked:
            if keyword in cleaned:
                return False

        # Block multiple statements
        if ';' in query[:-1]:
            return False

        if '--' in query or '/*' in query:
            return False

        return True

    def _is_valid_table_name(self, table_name: str) -> bool:
        """Validate table name to prevent SQL injection."""
        # Only allow alphanumeric and underscore
        return bool(re.match(r'^[a-zA-Z0-9_]+$', table_name))
