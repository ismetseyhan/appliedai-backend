"""
User Service
Handles user business logic.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.entities.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    """Service for user business logic."""

    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self.repository.get_by_id(user_id)

    def get_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        """Get user by Firebase UID."""
        return self.repository.get_by_firebase_uid(firebase_uid)

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.repository.get_by_email(email)

    def create_user(self, firebase_uid: str, email: str, display_name: Optional[str] = None) -> User:
        """
        Create a new user.

        Args:
            firebase_uid: Firebase user ID
            email: User email
            display_name: Optional display name

        Returns:
            Created user entity
        """
        user = User(
            id=firebase_uid,
            email=email,
            display_name=display_name
        )
        return self.repository.create(user)

    def user_exists(self, firebase_uid: str) -> bool:
        """Check if user exists by Firebase UID."""
        return self.repository.get_by_firebase_uid(firebase_uid) is not None
