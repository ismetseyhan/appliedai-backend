"""
Text-to-SQL Agent Schemas
Request/response models for natural language to SQL conversion.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any


class TextToSQLRequest(BaseModel):
    """Request schema for text-to-SQL conversion"""
    query: str = Field(..., min_length=1, description="Natural language query")
    max_sql_queries: int = Field(3, ge=1, le=10, description="Maximum SQL queries to execute")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Show me the top 10 highest rated movies",
                "max_sql_queries": 3
            }
        }


class AgentStep(BaseModel):
    """Single step in agent reasoning process"""
    step_number: int = Field(..., description="Step number in execution")
    action: str = Field(..., description="Action taken (e.g., execute_sql_query)")
    action_input: str = Field(..., description="Input to the action (e.g., SQL query)")
    observation: str = Field(..., description="Result/observation from the action")

#example response
class TextToSQLResponse(BaseModel):
    """Response schema for text-to-SQL conversion"""
    query: str = Field(..., description="Original user query")
    final_answer: str = Field(..., description="Natural language answer from agent")
    sql_queries: List[str] = Field(..., description="List of SQL queries executed")
    results: List[Any] = Field(..., description="Query results (columns, rows, row_count)")
    steps: List[AgentStep] = Field(..., description="Detailed reasoning steps")
    execution_time_ms: int = Field(..., description="Total execution time in milliseconds")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Show top 10 movies",
                "final_answer": "Here are the top 10 highest rated movies from the database...",
                "sql_queries": ["SELECT movie_title, imdb_rating FROM movies ORDER BY imdb_rating DESC LIMIT 10"],
                "results": [{"columns": ["movie_title", "imdb_rating"], "rows": [...], "row_count": 10}],
                "steps": [
                    {
                        "step_number": 1,
                        "action": "execute_sql_query",
                        "action_input": "SELECT movie_title, imdb_rating FROM movies ORDER BY imdb_rating DESC LIMIT 10",
                        "observation": "Query returned 10 rows"
                    }
                ],
                "execution_time_ms": 1234
            }
        }
