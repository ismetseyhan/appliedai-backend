from app.repositories.user_preferences_repository import UserPreferencesRepository


class UserPreferencesService:
    """Service for managing user preferences."""

    QUERY_CHECKER_ENABLED = "query_checker_enabled"

    DEFAULTS = {
        QUERY_CHECKER_ENABLED: "true",
    }

    def __init__(self, repository: UserPreferencesRepository):
        self.repository = repository

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
