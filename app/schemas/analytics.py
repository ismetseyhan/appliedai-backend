"""
Analytics Schemas - Pydantic models for dashboard analytics
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


class MetricTrend(BaseModel):
    """Trend information for a metric"""
    direction: Literal["up", "down", "neutral"]
    percentage: float
    display_text: str  # e.g., "+12% from yesterday", "-8% faster"


class DashboardMetric(BaseModel):
    """Single dashboard metric with trend"""
    title: str
    value: str  # Formatted string (e.g., "1,247", "98.5%", "1.2s")
    raw_value: float  # Raw numeric value for calculations
    trend: Optional[MetricTrend] = None
    color: str  # Hex color code


class RecentActivityItem(BaseModel):
    """Single recent activity item"""
    id: str
    query: str  # User's question
    agent: str  # Primary agent used (first in agents_called)
    agents_called: List[str]  # All agents used
    status: Literal["success", "failed"]
    execution_time_ms: Optional[int]
    created_at: datetime


class DashboardMetricsResponse(BaseModel):
    """Complete dashboard metrics response"""
    total_requests: DashboardMetric
    active_agents: DashboardMetric
    avg_response_time: DashboardMetric
    success_rate: DashboardMetric

    class Config:
        json_schema_extra = {
            "example": {
                "total_requests": {
                    "title": "Total Requests",
                    "value": "1,247",
                    "raw_value": 1247,
                    "trend": {
                        "direction": "up",
                        "percentage": 12.0,
                        "display_text": "+12% from yesterday"
                    },
                    "color": "#2196f3"
                },
                "active_agents": {
                    "title": "Active Agents",
                    "value": "3",
                    "raw_value": 3,
                    "trend": None,
                    "color": "#4caf50"
                },
                "avg_response_time": {
                    "title": "Avg Response Time",
                    "value": "1.2s",
                    "raw_value": 1.2,
                    "trend": {
                        "direction": "down",
                        "percentage": 8.0,
                        "display_text": "-8% faster"
                    },
                    "color": "#ff9800"
                },
                "success_rate": {
                    "title": "Success Rate",
                    "value": "98.5%",
                    "raw_value": 98.5,
                    "trend": {
                        "direction": "up",
                        "percentage": 2.1,
                        "display_text": "+2.1%"
                    },
                    "color": "#4caf50"
                }
            }
        }


class RecentActivityResponse(BaseModel):
    """Paginated recent activity response"""
    items: List[RecentActivityItem]
    total: int
    limit: int
    offset: int
