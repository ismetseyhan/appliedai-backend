from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.config import settings
from app.entities.user import User
from app.services.firebase_storage import FirebaseStorageService
from app.services.document_service import DocumentService
from app.services.sqlite_service import SQLiteService
from app.repositories.sqlite_database_repository import SQLiteDatabaseRepository

# HTTPBearer security scheme for Swagger UI
security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your Firebase ID token"
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Verify Firebase token and return user from database

    Expects: Authorization: Bearer <firebase_token>
    """
    # Get token from credentials
    token = credentials.credentials

    # Verify Firebase token
    decoded_token = verify_firebase_token(token)
    if not decoded_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    # Get user from database
    firebase_uid = decoded_token.get("uid")
    user = db.query(User).filter(User.id == firebase_uid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please register first."
        )

    return user


def get_storage_service() -> FirebaseStorageService:
    """Dependency: Get Firebase Storage Service instance."""
    return FirebaseStorageService(settings.FIREBASE_STORAGE_BUCKET)


def get_document_service(
    db: Session = Depends(get_db),
    storage_service: FirebaseStorageService = Depends(get_storage_service)
) -> DocumentService:
    """Dependency: Get Document Service instance."""
    return DocumentService(db=db, storage_service=storage_service)


def get_sqlite_service(
    db: Session = Depends(get_db),
    storage_service: FirebaseStorageService = Depends(get_storage_service)
) -> SQLiteService:
    """Dependency: Get SQLite Service instance"""
    db_repository = SQLiteDatabaseRepository(db=db)
    return SQLiteService(storage_service=storage_service, db_repository=db_repository)
