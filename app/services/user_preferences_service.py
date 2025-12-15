from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.user_preferences_repository import UserPreferencesRepository
from app.repositories.document_chunking_repository import DocumentChunkingRepository


class UserPreferencesService:
    """Service for managing user preferences."""

    QUERY_CHECKER_ENABLED = "query_checker_enabled"
    ACTIVE_RAG_DATA = "active_rag_data"

    DEFAULTS = {
        QUERY_CHECKER_ENABLED: "true",
    }

    def __init__(self, db: Session):
        self.repository = UserPreferencesRepository(db)
        self.chunking_repository = DocumentChunkingRepository(db)

    def get_query_checker_enabled(self, user_id: str) -> bool:
        preference = self.repository.get_preference(user_id, self.QUERY_CHECKER_ENABLED)
        if preference:
            return preference.preference_value.lower() == "true"
        return self.DEFAULTS[self.QUERY_CHECKER_ENABLED].lower() == "true"

    def set_query_checker_enabled(self, user_id: str, enabled: bool) -> None:
        self.repository.upsert_preference(
            user_id=user_id,
            preference_key=self.QUERY_CHECKER_ENABLED,
            preference_value="true" if enabled else "false"
        )

    def get_all_preferences(self, user_id: str) -> dict:
        preferences = self.repository.get_user_preferences(user_id)
        result = self.DEFAULTS.copy()
        for pref in preferences:
            result[pref.preference_key] = pref.preference_value
        return result

    def get_active_rag_data(self, user_id: str) -> str | None:
        preference = self.repository.get_preference(user_id, self.ACTIVE_RAG_DATA)
        return preference.preference_value if preference else None

    def set_active_rag_data(self, user_id: str, document_chunking_id: str) -> None:
        self.repository.upsert_preference(
            user_id=user_id,
            preference_key=self.ACTIVE_RAG_DATA,
            preference_value=document_chunking_id
        )

    def get_or_auto_select_rag_data(self, user_id: str) -> Optional[str]:
        """
        Get active RAG data. If not set, auto-select first available is_active=true record.
        """
        active_id = self.get_active_rag_data(user_id)
        if active_id:
            # Validate: chunks exist + prompt exists + user has access
            chunk_config = self.chunking_repository.get_by_id_if_active_and_accessible(
                active_id, user_id
            )
            if chunk_config:
                return active_id

        # Find first available is_active=true chunking
        chunk_config = self.chunking_repository.get_first_active_accessible(user_id)

        if chunk_config:
            # Save to preferences
            self.set_active_rag_data(user_id, chunk_config.id)
            return chunk_config.id

        return None
