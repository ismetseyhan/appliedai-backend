from sqlalchemy import Column, String, BigInteger, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class SQLiteDatabase(Base):
    __tablename__ = "sqlite_databases"

    id = Column(String, primary_key=True, default=generate_uuid)
    database_name = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    storage_path = Column(String, nullable=False, unique=True, index=True)
    allowed_operations = Column(
        JSONB,
        nullable=False,
        default=lambda: ["SELECT", "INSERT", "UPDATE", "DELETE"]
    )
    sql_agent_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<SQLiteDatabase {self.database_name}>"
