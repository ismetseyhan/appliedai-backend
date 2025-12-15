"""
Conversation Service
"""
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.entities.conversation import Conversation, ConversationMessage
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.orchestrator import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationMessage as ConversationMessageSchema,
    ConversationListResponse
)


class ConversationService:

    def __init__(self, db: Session):
        self.conversation_repository = ConversationRepository(db)

    def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
        default_title: str
    ) -> Conversation:

        if conversation_id:
            conversation = self.conversation_repository.get_conversation(conversation_id)
            if conversation and conversation.user_id == user_id:
                return conversation

        return self._create_conversation(user_id, default_title)

    def add_user_message(
        self,
        conversation_id: str,
        content: str
    ) -> ConversationMessage:
        """Add user message to conversation."""
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=content,
            agent_metadata=None
        )
        self.conversation_repository.add_message(message)
        return message

    def add_assistant_message(
        self,
        conversation_id: str,
        content: str,
        agent_metadata: Dict[str, Any]
    ) -> ConversationMessage:
        """Add assistant message to conversation."""
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            agent_metadata=agent_metadata
        )
        self.conversation_repository.add_message(message)
        self.conversation_repository.update_conversation_timestamp(conversation_id)
        return message

    def get_conversation_history(
        self,
        conversation_id: str,
        exclude_last: bool = False
    ) -> List[Dict[str, str]]:

        messages = self.conversation_repository.get_conversation_messages(conversation_id)

        if exclude_last and messages:
            messages = messages[:-1]

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    def create_conversation(
        self,
        user_id: str,
        request: ConversationCreateRequest
    ) -> ConversationResponse:

        conversation = self._create_conversation(user_id, request.title)
        return self._conversation_to_response(conversation)

    def get_user_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> ConversationListResponse:

        conversations = self.conversation_repository.get_user_conversations(
            user_id, limit, offset
        )

        conversation_responses = []
        for conv in conversations:
            messages = self.conversation_repository.get_conversation_messages(conv.id)
            conversation_responses.append(ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                title=conv.title,
                message_count=len(messages),
                created_at=conv.created_at,
                updated_at=conv.updated_at
            ))

        total = len(conversation_responses)

        return ConversationListResponse(
            conversations=conversation_responses,
            total=total,
            limit=limit,
            offset=offset
        )

    def get_conversation_detail(
        self,
        user_id: str,
        conversation_id: str
    ) -> Optional[ConversationDetailResponse]:
        """Get conversation with messages."""
        conversation = self.conversation_repository.get_conversation(conversation_id)

        if not conversation or conversation.user_id != user_id:
            return None

        messages = self.conversation_repository.get_conversation_messages(conversation_id)

        message_schemas = [
            ConversationMessageSchema(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                agent_metadata=msg.agent_metadata,
                created_at=msg.created_at
            )
            for msg in messages
        ]

        return ConversationDetailResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            messages=message_schemas,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )

    def delete_conversation(
        self,
        user_id: str,
        conversation_id: str
    ) -> bool:
        """Delete a conversation."""
        conversation = self.conversation_repository.get_conversation(conversation_id)

        if not conversation or conversation.user_id != user_id:
            return False

        self.conversation_repository.delete_conversation(conversation)
        return True

    def _create_conversation(self, user_id: str, title: str) -> Conversation:
        """Create a new conversation entity."""
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title[:200]
        )
        return self.conversation_repository.create_conversation(conversation)

    def _conversation_to_response(self, conversation: Conversation) -> ConversationResponse:
        """Convert conversation entity to response schema."""
        messages = self.conversation_repository.get_conversation_messages(conversation.id)
        return ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            message_count=len(messages),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
