"""
Agent Health Check Service
"""
from sqlalchemy.orm import Session
from app.core.config import settings
from app.schemas.agent_health import AgentHealthStatus, SystemHealthResponse
from app.repositories.sqlite_database_repository import SQLiteDatabaseRepository
from app.repositories.document_chunking_repository import DocumentChunkingRepository


class AgentHealthService:

    def __init__(self, db: Session):
        self.db = db
        self.config = settings

    def check_research_agent_health(self) -> AgentHealthStatus:
        """Check if Google Search API keys are configured"""
        api_key = self.config.GOOGLE_SEARCH_API_KEY
        engine_id = self.config.GOOGLE_SEARCH_ENGINE_ID

        if not api_key or not engine_id:
            return AgentHealthStatus(
                agent_name="Research Agent",
                status="not_configured",
                message="Google Search API keys not configured"
            )

        return AgentHealthStatus(
            agent_name="Research Agent",
            status="healthy",
            message="Google Search configured"
        )

    def check_text_to_sql_agent_health(self, user_id: str) -> AgentHealthStatus:
        """Check if database is uploaded and SQL agent prompt exists"""
        repo = SQLiteDatabaseRepository(self.db)
        db_record = repo.get_current_database()

        if not db_record:
            return AgentHealthStatus(
                agent_name="Text-to-SQL Agent",
                status="no_database",
                message="No database uploaded"
            )

        if not db_record.sql_agent_prompt:
            return AgentHealthStatus(
                agent_name="Text-to-SQL Agent",
                status="no_prompt",
                message="SQL agent prompt not generated"
            )

        return AgentHealthStatus(
            agent_name="Text-to-SQL Agent",
            status="healthy",
            message=f"Database '{db_record.database_name}' ready"
        )

    def check_rag_agent_health(self, user_id: str) -> AgentHealthStatus:
        """Check if user has active document chunking processes own + public"""
        repo = DocumentChunkingRepository(self.db)
        results = repo.get_with_chunk_count(user_id)

        active_processes = [
            (doc_template, chunk_count)
            for doc_template, chunk_count, _, _, _ in results
            if (
                doc_template.is_active and
                doc_template.agent_prompt and
                chunk_count > 0
            )
        ]

        if not active_processes:
            return AgentHealthStatus(
                agent_name="RAG Agent",
                status="no_active_processes",
                message="No active document chunking processes"
            )

        return AgentHealthStatus(
            agent_name="RAG Agent",
            status="healthy",
            message=f"{len(active_processes)} active process(es)"
        )

    def get_system_health(self, user_id: str) -> SystemHealthResponse:
        """Get overall system health status"""
        research = self.check_research_agent_health()
        text_to_sql = self.check_text_to_sql_agent_health(user_id)
        rag = self.check_rag_agent_health(user_id)

        # Determine overall status
        healthy_count = sum([
            research.status == "healthy",
            text_to_sql.status == "healthy",
            rag.status == "healthy"
        ])

        if healthy_count == 3:
            overall = "healthy"
        elif healthy_count > 0:
            overall = "partial"
        else:
            overall = "unhealthy"

        return SystemHealthResponse(
            overall_status=overall,
            research_agent=research,
            text_to_sql_agent=text_to_sql,
            rag_agent=rag
        )
