"""
Analytics Repository - Database operations for dashboard analytics
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Integer, and_, text
from datetime import datetime

from app.entities.conversation import Conversation, ConversationMessage


class AnalyticsRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_total_requests(self, user_id: str, start_date: datetime, end_date: datetime) -> int:
        """
        Count total user messages in time range.

        Returns count of user messages (role='user')
        """
        count = self.db.query(func.count(ConversationMessage.id)).join(
            Conversation,
            ConversationMessage.conversation_id == Conversation.id
        ).filter(
            and_(
                Conversation.user_id == user_id,
                ConversationMessage.role == 'user',
                ConversationMessage.created_at >= start_date,
                ConversationMessage.created_at < end_date
            )
        ).scalar()

        return count or 0

    def get_unique_agents(self, user_id: str) -> List[str]:
        """
        Extract unique agent names from agent_metadata->agents_called.
        """
        # Use raw SQL for JSONB array operations
        query = text("""
            SELECT DISTINCT jsonb_array_elements_text(agent_metadata->'agents_called') AS agent_name
            FROM conversation_messages cm
            JOIN conversations c ON cm.conversation_id = c.id
            WHERE c.user_id = :user_id
            AND cm.role = 'assistant'
            AND cm.agent_metadata IS NOT NULL
            AND cm.agent_metadata->'agents_called' IS NOT NULL
        """)

        result = self.db.execute(query, {"user_id": user_id})
        agents = [row[0] for row in result if row[0]]  # Extract agent names

        return agents

    def get_avg_execution_time(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[float]:
        """
        Calculate average execution time from agent_metadata->execution_time_ms.
        """
        query = text("""
            SELECT AVG((agent_metadata->>'execution_time_ms')::INTEGER) AS avg_time_ms
            FROM conversation_messages cm
            JOIN conversations c ON cm.conversation_id = c.id
            WHERE c.user_id = :user_id
            AND cm.role = 'assistant'
            AND cm.agent_metadata IS NOT NULL
            AND cm.agent_metadata->>'execution_time_ms' IS NOT NULL
            AND cm.created_at >= :start_date
            AND cm.created_at < :end_date
        """)

        result = self.db.execute(query, {
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date
        })

        avg_time = result.scalar()
        return float(avg_time) if avg_time else None

    def get_success_rate(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, int]:
        """
        Calculate success rate (user messages vs assistant responses).
        """
        query = text("""
            SELECT
                COUNT(*) FILTER (WHERE cm.role = 'user') AS total_requests,
                COUNT(*) FILTER (WHERE cm.role = 'assistant') AS successful_requests
            FROM conversation_messages cm
            JOIN conversations c ON cm.conversation_id = c.id
            WHERE c.user_id = :user_id
            AND cm.created_at >= :start_date
            AND cm.created_at < :end_date
        """)

        result = self.db.execute(query, {
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date
        }).fetchone()

        return {
            "total": result[0] if result else 0,
            "successful": result[1] if result else 0
        }

    def get_recent_activity(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get recent user messages with pagination.
        """
        # Get total count
        total_count = self.db.query(func.count(ConversationMessage.id)).join(
            Conversation,
            ConversationMessage.conversation_id == Conversation.id
        ).filter(
            and_(
                Conversation.user_id == user_id,
                ConversationMessage.role == 'user'
            )
        ).scalar() or 0

        # Get paginated items
        messages = self.db.query(ConversationMessage).join(
            Conversation,
            ConversationMessage.conversation_id == Conversation.id
        ).filter(
            and_(
                Conversation.user_id == user_id,
                ConversationMessage.role == 'user'
            )
        ).order_by(ConversationMessage.created_at.desc()).limit(limit).offset(offset).all()


        items = []
        for message in messages:
            assistant_message = self.db.query(ConversationMessage).filter(
                and_(
                    ConversationMessage.conversation_id == message.conversation_id,
                    ConversationMessage.role == 'assistant',
                    ConversationMessage.created_at > message.created_at
                )
            ).order_by(ConversationMessage.created_at.asc()).first()
            agents_called = []
            execution_time_ms = None
            status = "failed"

            if assistant_message and assistant_message.agent_metadata:
                agents_called = assistant_message.agent_metadata.get("agents_called", [])
                execution_time_ms = assistant_message.agent_metadata.get("execution_time_ms")
                status = "success"

            items.append({
                "id": message.id,
                "query": message.content,
                "agents_called": agents_called,
                "execution_time_ms": execution_time_ms,
                "status": status,
                "created_at": message.created_at
            })

        return items, total_count
