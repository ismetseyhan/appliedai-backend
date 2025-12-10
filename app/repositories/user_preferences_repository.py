from typing import Optional
from sqlalchemy.orm import Session
from app.entities.user_preference import UserPreference


class UserPreferencesRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_preference(self, user_id: str, preference_key: str) -> Optional[UserPreference]:
        """Get a specific preference for a user."""
        return self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id,
            UserPreference.preference_key == preference_key
        ).first()

    def get_user_preferences(self, user_id: str) -> list[UserPreference]:
        """Get all preferences for a user."""
        return self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).all()

    def upsert_preference(self, user_id: str, preference_key: str, preference_value: str) -> UserPreference:
        """Create or update a preference."""
        preference = self.get_preference(user_id, preference_key)
        if preference:
            preference.preference_value = preference_value
        else:
            preference = UserPreference(
                user_id=user_id,
                preference_key=preference_key,
                preference_value=preference_value
            )
            self.db.add(preference)
        self.db.commit()
        self.db.refresh(preference)
        return preference

    def delete_preference(self, user_id: str, preference_key: str) -> bool:
        """Delete a preference."""
        preference = self.get_preference(user_id, preference_key)
        if preference:
            self.db.delete(preference)
            self.db.commit()
            return True
        return False
