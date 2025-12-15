from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from app.entities.conversation import Conversation, ConversationMessage


class ConversationRepository:
    """Repository for Conversation database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_conversation(self, conversation: Conversation) -> Conversation:
        """Create a new conversation."""
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get_conversation(
        self,
        conversation_id: str,
        load_messages: bool = False
    ) -> Optional[Conversation]:
        """Get conversation by ID."""
        query = self.db.query(Conversation)
        if load_messages:
            query = query.options(joinedload(Conversation.messages))
        return query.filter(Conversation.id == conversation_id).first()

    def get_user_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Conversation]:
        """Get all conversations for a user."""
        return self.db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(
            Conversation.updated_at.desc(),
            Conversation.created_at.desc()
        ).limit(limit).offset(offset).all()

    def delete_conversation(self, conversation: Conversation) -> None:
        """Delete a conversation (cascades to messages)."""
        self.db.delete(conversation)
        self.db.commit()

    def add_message(
        self,
        message: ConversationMessage
    ) -> ConversationMessage:
        """Add a message to a conversation."""
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_conversation_messages(
        self,
        conversation_id: str
    ) -> List[ConversationMessage]:
        """Get all messages for a conversation."""
        return self.db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).order_by(
            ConversationMessage.created_at.asc()
        ).all()

    def update_conversation_timestamp(
        self,
        conversation_id: str
    ) -> Optional[Conversation]:
        """Update conversation's updated_at timestamp."""
        conversation = self.get_conversation(conversation_id)
        if conversation:
            from sqlalchemy.sql import func
            conversation.updated_at = func.now()
            self.db.commit()
            self.db.refresh(conversation)
        return conversation
