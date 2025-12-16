from typing import TYPE_CHECKING
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.config import settings

if TYPE_CHECKING:
    from app.entities.user import User
from app.services.firebase_storage_service import FirebaseStorageService
from app.services.document_service import DocumentService
from app.services.sqlite_service import SQLiteService
from app.services.llm_service import LLMService
from app.services.google_search_service import GoogleSearchService
from app.services.user_preferences_service import UserPreferencesService
from app.services.template_service import TemplateService
from app.services.llm_template_generator_service import LLMTemplateGeneratorService
from app.services.chunking_processor_service import ChunkingProcessorService
from app.services.document_chunking_service import DocumentChunkingService
from app.services.rag_service import RAGService
from app.services.rag_prompt_service import RagPromptService
from app.services.rag_prompt_generator_service import RagPromptGeneratorService
from app.services.conversation_service import ConversationService
from app.services.user_service import UserService
from app.services.orchestrator_service import OrchestratorService
from app.services.analytics_service import AnalyticsService

# HTTPBearer security scheme for Swagger UI
security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your Firebase ID token"
)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Dependency: Get User Service instance."""
    return UserService(db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service)
) -> "User":
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
    user = user_service.get_by_firebase_uid(firebase_uid)

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
    return SQLiteService(storage_service=storage_service, db=db)

def get_llm_service() -> LLMService:
    """Dependency: Get LLM Service instance (uses default OPENAI_MODEL_NAME)."""
    return LLMService()

def get_text_to_sql_llm_service() -> LLMService:
    """Dependency: Get LLM Service for Text-to-SQL agent."""
    return LLMService(model_name=settings.get_text_to_sql_model())


def get_rag_llm_service() -> LLMService:
    """Dependency: Get LLM Service for RAG agent."""
    return LLMService(model_name=settings.get_rag_model())


def get_research_llm_service() -> LLMService:
    """Dependency: Get LLM Service for Research agent."""
    return LLMService(model_name=settings.get_research_model())


def get_orchestrator_llm_service() -> LLMService:
    """Dependency: Get LLM Service for Orchestrator agent."""
    return LLMService(model_name=settings.get_orchestrator_model())


def get_user_preferences_service(db: Session = Depends(get_db)) -> UserPreferencesService:
    """Dependency: Get User Preferences Service instance."""
    return UserPreferencesService(db)


def get_google_search_service() -> GoogleSearchService:
    """Dependency: Get Google Search Service instance."""
    return GoogleSearchService(
        api_key=settings.GOOGLE_SEARCH_API_KEY,
        engine_id=settings.GOOGLE_SEARCH_ENGINE_ID,
        max_results=settings.GOOGLE_SEARCH_MAX_RESULTS
    )


def get_template_service(
    db: Session = Depends(get_db),
    storage_service: FirebaseStorageService = Depends(get_storage_service),
    llm_service: LLMService = Depends(get_llm_service)
) -> TemplateService:
    """Dependency: Get Template Service instance."""
    llm_generator = LLMTemplateGeneratorService(llm_service)
    return TemplateService(
        db=db,
        storage_service=storage_service,
        llm_generator_service=llm_generator
    )


def get_chunking_service(
    db: Session = Depends(get_db),
    storage_service: FirebaseStorageService = Depends(get_storage_service),
    llm_service: LLMService = Depends(get_llm_service)
) -> ChunkingProcessorService:
    """Dependency: Get Chunking Service instance."""
    return ChunkingProcessorService(db=db, storage_service=storage_service, llm_service=llm_service)


def get_document_chunking_service(
    db: Session = Depends(get_db),
    chunking_processor: ChunkingProcessorService = Depends(get_chunking_service)
) -> DocumentChunkingService:
    """Dependency: Get Document Chunking Service instance."""
    return DocumentChunkingService(db=db, chunking_processor=chunking_processor)


def get_rag_service(
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_rag_llm_service),
    preferences_service: UserPreferencesService = Depends(get_user_preferences_service)
) -> RAGService:
    """Dependency: Get RAG Service instance."""
    return RAGService(
        db=db,
        llm_service=llm_service,
        preferences_service=preferences_service
    )


def get_rag_prompt_service(
    db: Session = Depends(get_db),
    preferences_service: UserPreferencesService = Depends(get_user_preferences_service)
) -> RagPromptService:
    """Dependency: Get RAG Prompt Service instance."""
    return RagPromptService(
        db=db,
        preferences_service=preferences_service
    )


def get_rag_prompt_generator_service(
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service)
) -> RagPromptGeneratorService:
    """Dependency: Get RAG Prompt Generator Service instance."""
    return RagPromptGeneratorService(llm_service, db)


def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
    """Dependency: Get Conversation Service instance."""
    return ConversationService(db)


def get_orchestrator_service(
    db: Session = Depends(get_db),
    conversation_service: ConversationService = Depends(get_conversation_service),
    sqlite_service: SQLiteService = Depends(get_sqlite_service),
    llm_service: LLMService = Depends(get_orchestrator_llm_service),
    google_search_service: GoogleSearchService = Depends(get_google_search_service),
    preferences_service: UserPreferencesService = Depends(get_user_preferences_service),
    rag_service: RAGService = Depends(get_rag_service)
) -> OrchestratorService:
    """Dependency: Get Orchestrator Service instance."""
    return OrchestratorService(
        conversation_service=conversation_service,
        sqlite_service=sqlite_service,
        llm_service=llm_service,
        google_search_service=google_search_service,
        preferences_service=preferences_service,
        rag_service=rag_service,
        db=db
    )


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    """Dependency: Get Analytics Service instance."""
    return AnalyticsService(db)


def get_agent_health_service(db: Session = Depends(get_db)) -> 'AgentHealthService':
    """Dependency: Get Agent Health Service instance."""
    from app.services.agent_health_service import AgentHealthService
    return AgentHealthService(db)
