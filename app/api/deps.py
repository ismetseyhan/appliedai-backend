from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.config import settings
from app.entities.user import User
from app.services.firebase_storage_service import FirebaseStorageService
from app.services.document_service import DocumentService
from app.services.sqlite_service import SQLiteService
from app.services.llm_service import LLMService
from app.services.google_search_service import GoogleSearchService
from app.repositories.sqlite_database_repository import SQLiteDatabaseRepository
from app.repositories.user_preferences_repository import UserPreferencesRepository
from app.services.user_preferences_service import UserPreferencesService

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

def get_llm_service() -> LLMService:
    """Dependency: Get LLM Service instance."""
    return LLMService()


def get_user_preferences_service(db: Session = Depends(get_db)) -> UserPreferencesService:
    """Dependency: Get User Preferences Service instance."""
    repository = UserPreferencesRepository(db)
    return UserPreferencesService(repository)


def get_google_search_service() -> GoogleSearchService:
    """Dependency: Get Google Search Service instance."""
    return GoogleSearchService(
        api_key=settings.GOOGLE_SEARCH_API_KEY,
        engine_id=settings.GOOGLE_SEARCH_ENGINE_ID,
        max_results=settings.GOOGLE_SEARCH_MAX_RESULTS
    )
