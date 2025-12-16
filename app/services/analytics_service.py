"""
Analytics Service
"""
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.analytics import (
    DashboardMetricsResponse,
    DashboardMetric,
    MetricTrend,
    RecentActivityResponse,
    RecentActivityItem
)


class AnalyticsService:


    def __init__(self, db: Session):
        self.analytics_repository = AnalyticsRepository(db)

    def get_dashboard_metrics(self, user_id: str) -> DashboardMetricsResponse:

        # Calculate date ranges
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start

        # Get today's metrics
        total_requests_today = self.analytics_repository.get_total_requests(
            user_id, today_start, today_end
        )
        avg_time_today = self.analytics_repository.get_avg_execution_time(
            user_id, today_start, today_end
        )
        success_data_today = self.analytics_repository.get_success_rate(
            user_id, today_start, today_end
        )

        # Get yesterday's metrics for trends
        total_requests_yesterday = self.analytics_repository.get_total_requests(
            user_id, yesterday_start, yesterday_end
        )
        avg_time_yesterday = self.analytics_repository.get_avg_execution_time(
            user_id, yesterday_start, yesterday_end
        )
        success_data_yesterday = self.analytics_repository.get_success_rate(
            user_id, yesterday_start, yesterday_end
        )

        # Get unique agents (all time)
        unique_agents = self.analytics_repository.get_unique_agents(user_id)

        # Calculate success rates
        success_rate_today = self._calculate_success_percentage(
            success_data_today["total"],
            success_data_today["successful"]
        )
        success_rate_yesterday = self._calculate_success_percentage(
            success_data_yesterday["total"],
            success_data_yesterday["successful"]
        )

        # Build response
        return DashboardMetricsResponse(
            total_requests=DashboardMetric(
                title="Total Requests",
                value=self._format_number(total_requests_today),
                raw_value=float(total_requests_today),
                trend=self._calculate_trend(
                    total_requests_today,
                    total_requests_yesterday,
                    "from yesterday"
                ),
                color="#2196f3"
            ),
            active_agents=DashboardMetric(
                title="Active Agents",
                value=str(len(unique_agents)),
                raw_value=float(len(unique_agents)),
                trend=None,  # No trend for static count
                color="#4caf50"
            ),
            avg_response_time=DashboardMetric(
                title="Avg Response Time",
                value=self._format_time(avg_time_today),
                raw_value=float(avg_time_today or 0),
                trend=self._calculate_trend(
                    avg_time_today or 0,
                    avg_time_yesterday or 0,
                    "",
                    inverse=True  # Lower is better for time
                ),
                color="#ff9800"
            ),
            success_rate=DashboardMetric(
                title="Success Rate",
                value=f"{success_rate_today:.1f}%",
                raw_value=success_rate_today,
                trend=self._calculate_trend(
                    success_rate_today,
                    success_rate_yesterday,
                    ""  # Just percentage change
                ),
                color="#4caf50"
            )
        )

    def get_recent_activity(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> RecentActivityResponse:
        """Get paginated recent activity"""
        items_data, total_count = self.analytics_repository.get_recent_activity(
            user_id, limit, offset
        )

        # Convert to Pydantic models
        items = []
        for item in items_data:
            agents_called = item["agents_called"]
            primary_agent = agents_called[0] if agents_called else "Unknown"

            items.append(RecentActivityItem(
                id=item["id"],
                query=item["query"],
                agent=primary_agent,
                agents_called=agents_called,
                status=item["status"],
                execution_time_ms=item["execution_time_ms"],
                created_at=item["created_at"]
            ))

        return RecentActivityResponse(
            items=items,
            total=total_count,
            limit=limit,
            offset=offset
        )

    # Helper methods

    def _calculate_trend(
        self,
        today_value: float,
        yesterday_value: float,
        suffix: str = "",
        inverse: bool = False
    ) -> Optional[MetricTrend]:
        """
        Calculate trend direction and percentage.
        """
        if yesterday_value == 0:
            if today_value == 0:
                return None  # No change, both zero
            return MetricTrend(
                direction="up",  # first data
                percentage=100.0,
                display_text=f"+100% {suffix}".strip()
            )


        percentage = ((today_value - yesterday_value) / yesterday_value) * 100


        if inverse:

            direction = "down" if percentage < 0 else ("up" if percentage > 0 else "neutral")
        else:

            direction = "up" if percentage > 0 else ("down" if percentage < 0 else "neutral")

        # Format display text
        sign = "+" if percentage > 0 else ""
        display_text = f"{sign}{percentage:.1f}% {suffix}".strip()

        return MetricTrend(
            direction=direction,
            percentage=abs(percentage),
            display_text=display_text
        )

    def _calculate_success_percentage(self, total: int, successful: int) -> float:
        """Calculate success rate percentage"""
        if total == 0:
            return 100.0  # No requests = 100% success rate
        return (successful / total) * 100

    def _format_number(self, value: int) -> str:
        """Format number with thousands separator (e.g., 1,247)"""
        return f"{value:,}"

    def _format_time(self, milliseconds: Optional[float]) -> str:
        """Format time in milliseconds to seconds string (e.g., 1.2s)"""
        if milliseconds is None or milliseconds == 0:
            return "0s"
        seconds = milliseconds / 1000
        return f"{seconds:.1f}s"
