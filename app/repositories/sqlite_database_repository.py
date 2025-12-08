from sqlalchemy.orm import Session
from app.entities.sqlite_database import SQLiteDatabase
from typing import Optional


class SQLiteDatabaseRepository:
    """Repository for SQLite database."""

    def __init__(self, db: Session):
        self.db = db

    def get_current_database(self) -> Optional[SQLiteDatabase]:
        return self.db.query(SQLiteDatabase).first()

    def create_or_replace(
        self,
        database_name: str,
        file_size: int,
        storage_path: str = "sqlite/current.db",
        allowed_operations: list = None
    ) -> SQLiteDatabase:

        if allowed_operations is None:
            allowed_operations = ["SELECT", "INSERT", "UPDATE", "DELETE"]

        self.db.query(SQLiteDatabase).filter(
            SQLiteDatabase.storage_path == storage_path
        ).delete()


        db_record = SQLiteDatabase(
            database_name=database_name,
            file_size=file_size,
            storage_path=storage_path,
            allowed_operations=allowed_operations,
            sql_agent_prompt=None
        )
        self.db.add(db_record)
        self.db.commit()
        self.db.refresh(db_record)
        return db_record

    def update_allowed_operations(
        self,
        db_id: str,
        allowed_operations: list
    ) -> Optional[SQLiteDatabase]:
        db_record = self.db.query(SQLiteDatabase).filter(
            SQLiteDatabase.id == db_id
        ).first()

        if db_record:
            db_record.allowed_operations = allowed_operations
            self.db.commit()
            self.db.refresh(db_record)

        return db_record

    def delete(self, db_id: str) -> bool:
        result = self.db.query(SQLiteDatabase).filter(
            SQLiteDatabase.id == db_id
        ).delete()
        self.db.commit()
        return result > 0

    def delete_by_storage_path(self, storage_path: str) -> bool:
        result = self.db.query(SQLiteDatabase).filter(
            SQLiteDatabase.storage_path == storage_path
        ).delete()
        self.db.commit()
        return result > 0
