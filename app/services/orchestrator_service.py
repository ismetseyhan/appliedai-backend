"""
Orchestrator Service
Multi-agent orchestration logic.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.text_to_sql_agent import TextToSQLAgent
from app.agents.rag_agent import RAGAgent
from app.agents.research_agent import ResearchAgent
from app.services.llm_service import LLMService
from app.services.sqlite_service import SQLiteService
from app.services.google_search_service import GoogleSearchService
from app.services.user_preferences_service import UserPreferencesService
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService
from app.schemas.orchestrator import (
    OrchestratorQueryRequest,
    OrchestratorQueryResponse,
    AgentExecutionDetail
)


class OrchestratorService:
    """Service for multi-agent orchestration."""

    def __init__(
        self,
        conversation_service: ConversationService,
        sqlite_service: SQLiteService,
        llm_service: LLMService,
        google_search_service: GoogleSearchService,
        preferences_service: UserPreferencesService,
        rag_service: RAGService,
        db: Session
    ):
        self.conversation_service = conversation_service
        self.sqlite_service = sqlite_service
        self.llm_service = llm_service
        self.google_search_service = google_search_service
        self.preferences_service = preferences_service
        self.rag_service = rag_service
        self.db = db

    async def execute_query(
        self,
        user_id: str,
        request: OrchestratorQueryRequest
    ) -> OrchestratorQueryResponse:
        """Execute orchestrated query and save to conversation."""
        # Get or create conversation
        conversation = self.conversation_service.get_or_create_conversation(
            user_id=user_id,
            conversation_id=request.conversation_id,
            default_title=request.query[:100]
        )

        # Save user message
        self.conversation_service.add_user_message(
            conversation_id=conversation.id,
            content=request.query
        )

        # Load conversation history (excluding current message)
        conversation_history = self.conversation_service.get_conversation_history(
            conversation_id=conversation.id,
            exclude_last=True
        )

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

        # Build agent metadata
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
        self.conversation_service.add_assistant_message(
            conversation_id=conversation.id,
            content=result["final_answer"],
            agent_metadata=agent_metadata
        )

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

    def _create_rag_agent(self, user_id: str) -> Optional[RAGAgent]:
        """Create RAG agent using RAGService."""
        return self.rag_service.create_rag_agent(user_id)
