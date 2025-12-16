"""
Analytics API Endpoints
"""
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_analytics_service
from app.entities.user import User
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import (
    DashboardMetricsResponse,
    RecentActivityResponse
)


router = APIRouter()


@router.get(
    "/dashboard-metrics",
    response_model=DashboardMetricsResponse,
    summary="Get dashboard analytics metrics",
    description="Get all dashboard metrics for the current user including Total Requests, Active Agents, Avg Response Time, and Success Rate with trends (Today vs Yesterday)"
)
async def get_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get all dashboard metrics for the current user.
    """
    return analytics_service.get_dashboard_metrics(current_user.id)


@router.get(
    "/recent-activity",
    response_model=RecentActivityResponse,
    summary="Get recent user activity",
    description="Get paginated recent user activity with agent information and execution details"
)
async def get_recent_activity(
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Number of items to return per page"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset for pagination"
    ),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get paginated recent activity for the current user.
    """
    return analytics_service.get_recent_activity(
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )
