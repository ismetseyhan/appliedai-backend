"""
Orchestrator Service
"""
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.text_to_sql_agent import TextToSQLAgent
from app.agents.rag_agent import RAGAgent
from app.agents.research_agent import ResearchAgent
from app.entities.conversation import Conversation, ConversationMessage
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_chunking_repository import DocumentChunkingRepository
from app.services.llm_service import LLMService
from app.services.sqlite_service import SQLiteService
from app.services.google_search_service import GoogleSearchService
from app.services.user_preferences_service import UserPreferencesService
from app.schemas.orchestrator import (
    OrchestratorQueryRequest,
    OrchestratorQueryResponse,
    AgentExecutionDetail,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationMessage as ConversationMessageSchema,
    ConversationListResponse
)


class OrchestratorService:
    """Service for orchestrator operations and conversation management."""

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        chunk_repository: DocumentChunkRepository,
        chunking_repository: DocumentChunkingRepository,
        sqlite_service: SQLiteService,
        llm_service: LLMService,
        google_search_service: GoogleSearchService,
        preferences_service: UserPreferencesService,
        db: Session
    ):
        self.conversation_repository = conversation_repository
        self.chunk_repository = chunk_repository
        self.chunking_repository = chunking_repository
        self.sqlite_service = sqlite_service
        self.llm_service = llm_service
        self.google_search_service = google_search_service
        self.preferences_service = preferences_service
        self.db = db

    async def execute_query(
        self,
        user_id: str,
        request: OrchestratorQueryRequest
    ) -> OrchestratorQueryResponse:
        """Execute orchestrated query and save to conversation."""
        # Get or create conversation
        if request.conversation_id:
            conversation = self.conversation_repository.get_conversation(request.conversation_id)
            if not conversation or conversation.user_id != user_id:
                conversation = self._create_conversation(user_id, request.query[:100])
        else:

            conversation = self._create_conversation(user_id, request.query[:100])

        # Save user message
        user_message = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            role="user",
            content=request.query,
            agent_metadata=None
        )
        self.conversation_repository.add_message(user_message)

        # Load conversation history (excluding current message)
        all_messages = self.conversation_repository.get_conversation_messages(conversation.id)
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in all_messages[:-1]  # Exclude the message we just added
        ]

        # Initialize sub-agents
        sql_agent = TextToSQLAgent(
            self.sqlite_service,
            self.llm_service,
            self.preferences_service,
            user_id
        )

        research_agent = ResearchAgent(
            self.llm_service,
            self.google_search_service,
            user_id
        )

        rag_agent = self._create_rag_agent(user_id)

        orchestrator = OrchestratorAgent(
            llm_service=self.llm_service,
            sql_agent=sql_agent,
            research_agent=research_agent,
            rag_agent=rag_agent,
            user_id=user_id,
            db=self.db
        )

        result = await orchestrator.query(
            user_query=request.query,
            conversation_history=conversation_history,
            max_iterations=request.max_iterations
        )

        agent_metadata = {
            "agents_called": result["agents_called"],
            "execution_time_ms": result["execution_time_ms"],
            "mode_used": result["mode_used"],
            "agent_details": {
                name: {
                    "steps": detail["steps"],
                    "execution_time_ms": detail["execution_time_ms"],
                    "result_summary": detail["result_summary"],
                    "specific_data": detail.get("specific_data", {})
                }
                for name, detail in result["agent_details"].items()
            }
        }

        # Save assistant message
        assistant_message = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            role="assistant",
            content=result["final_answer"],
            agent_metadata=agent_metadata
        )
        self.conversation_repository.add_message(assistant_message)

        self.conversation_repository.update_conversation_timestamp(conversation.id)

        agent_details_response = {
            name: AgentExecutionDetail(**detail)
            for name, detail in result["agent_details"].items()
        }

        return OrchestratorQueryResponse(
            query=request.query,
            final_answer=result["final_answer"],
            agents_called=result["agents_called"],
            mode_used=result["mode_used"],
            agent_details=agent_details_response,
            execution_time_ms=result["execution_time_ms"],
            conversation_id=conversation.id
        )

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

        conversation = self.conversation_repository.get_conversation(conversation_id)

        if not conversation or conversation.user_id != user_id:
            return False

        self.conversation_repository.delete_conversation(conversation)
        return True

    def _create_conversation(self, user_id: str, title: str) -> Conversation:

        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title[:200]  # Truncate to max length
        )
        return self.conversation_repository.create_conversation(conversation)

    def _conversation_to_response(self, conversation: Conversation) -> ConversationResponse:

        messages = self.conversation_repository.get_conversation_messages(conversation.id)
        return ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            message_count=len(messages),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )

    def _create_rag_agent(self, user_id: str) -> Optional[RAGAgent]:

        active_id = self.preferences_service.get_or_auto_select_rag_data(user_id, self.db)
        if not active_id:
            return None

        doc_chunking = self.chunking_repository.get_by_id(active_id)
        if not doc_chunking or not doc_chunking.agent_prompt:
            return None

        return RAGAgent(
            chunk_repository=self.chunk_repository,
            llm_service=self.llm_service,
            document_chunking_id=active_id,
            agent_prompt=doc_chunking.agent_prompt
        )
