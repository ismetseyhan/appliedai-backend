"""
Text-to-SQL Agent
Stateless LangChain agent for natural language to SQL conversion.
Approach: LangChain validator + custom executor via SQLiteService.
"""
import json
import os
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit

from app.services.sqlite_service import SQLiteService
from app.services.llm_service import LLMService
from app.schemas.text_to_sql import TextToSQLResponse, AgentStep
from app.prompts.prompt_manager import SQL_AGENT_ENHANCED_PROMPT


class TextToSQLAgent:

    def __init__(self, sqlite_service: SQLiteService, llm_service: LLMService):
        self.sqlite_service = sqlite_service
        self.llm_service = llm_service
        self.sql_count = 0
        self.sql_queries = []
        self.results = []
        self._db = None  # Lazy-loaded SQLDatabase for LangChain

    def _get_sql_database(self) -> SQLDatabase:
        """Lazy-load SQLDatabase wrapper."""
        if self._db is None:
            db_path = self.sqlite_service.get_cached_db_path()
            if not db_path or not os.path.exists(db_path):
                raise ValueError("Database not cached locally")
            self._db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
        return self._db

    def _detect_operation(self, sql: str) -> str:
        """Detect SQL operation"""
        sql_upper = sql.strip().upper()

        if sql_upper.startswith("SELECT"):
            return "SELECT"
        elif sql_upper.startswith("INSERT"):
            return "INSERT"
        elif sql_upper.startswith("UPDATE"):
            return "UPDATE"
        elif sql_upper.startswith("DELETE"):
            return "DELETE"
        else:
            return "UNKNOWN"

    async def query(self, user_query: str, max_sql_queries: int = 3) -> TextToSQLResponse:
        """Convert natural language to SQL and execute safely."""
        # Reset state for new request
        self.sql_count = 0
        self.sql_queries = []
        self.results = []
        self.max_sql_queries = max_sql_queries

        llm = ChatOpenAI(
            model=self.llm_service.model_name,
            api_key=self.llm_service.api_key,
            temperature=0.0  # Deterministic for SQL generation
        )

        tools = self._get_tools()
        llm_with_tools = llm.bind_tools(tools)

        system_prompt = await self._get_system_prompt()
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("placeholder", "{messages}")  # history for error correction
        ])

        chain = prompt | llm_with_tools

        steps = []
        iteration = 0
        max_iterations = 5
        final_answer = None

        # Messages history for multi-step reasoning
        messages = [HumanMessage(content=user_query)]

        while iteration < max_iterations:
            iteration += 1

            # Send conversation history
            response = await chain.ainvoke({"messages": messages})

            # No tool calls = agent provided final answer
            if not response.tool_calls:
                final_answer = response.content
                break

            # Add agent response to history
            messages.append(response)

            # Process each tool call
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]

                if tool_name == "sql_db_query_checker":
                    # Validate SQL syntax via LangChain
                    query_checker = next((t for t in tools if t.name == "sql_db_query_checker"), None)
                    if query_checker:
                        observation = query_checker.invoke(tool_call["args"])
                    else:
                        observation = json.dumps({"error": "Query checker not available"})

                elif tool_name == "execute_sql_query":
                    sql = tool_call["args"]["sql"]

                    # Permission check
                    db_record = self.sqlite_service.db_repository.get_current_database()
                    operation = self._detect_operation(sql)

                    if operation not in db_record.allowed_operations:
                        observation = json.dumps({"error": f"{operation} operation not allowed"})

                    # SQL count limit check
                    elif self.sql_count >= self.max_sql_queries:
                        observation = json.dumps({"error": f"Maximum SQL query limit ({self.max_sql_queries}) reached"})

                    # Execute via SQLiteService
                    else:
                        try:
                            result = self.sqlite_service.execute_query(sql)
                            self.sql_count += 1
                            self.sql_queries.append(sql)

                            result_dict = {
                                "columns": result.columns,
                                "rows": result.rows,
                                "row_count": result.row_count
                            }
                            self.results.append(result_dict)
                            observation = json.dumps(result_dict)
                        except Exception as e:
                            observation = json.dumps({"error": str(e)})

                else:
                    observation = json.dumps({"error": f"Unknown tool: {tool_name}"})

                # Add tool result to conversation history
                messages.append(ToolMessage(
                    content=observation,
                    tool_call_id=tool_call.get("id", "unknown")
                ))

                # Track for frontend display
                steps.append(AgentStep(
                    step_number=len(steps) + 1,
                    action=tool_name,
                    action_input=str(tool_call["args"]),
                    observation=observation[:500]  # Truncate for response size
                ))

        # Synthesize natural language answer if queries executed
        if self.sql_count > 0 and not final_answer:
            synthesis_prompt = f"""Based on the query results, provide a clear natural language answer.

Original Question: {user_query}

Results: {json.dumps(self.results)}

Provide a concise, helpful answer:"""

            final_response = await llm.ainvoke(synthesis_prompt)
            final_answer = final_response.content

        if not final_answer:
            final_answer = "Could not generate answer within iteration limit"

        return TextToSQLResponse(
            query=user_query,
            final_answer=final_answer,
            sql_queries=self.sql_queries,
            results=self.results,
            steps=steps,
            execution_time_ms=0
        )

    def _get_tools(self) -> List:
        """Build tools: LangChain validator + custom executor."""
        db = self._get_sql_database()
        llm = ChatOpenAI(
            model=self.llm_service.model_name,
            api_key=self.llm_service.api_key,
            temperature=0.0 #deterministic
        )

        # Get LangChain SQL toolkit
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        all_tools = toolkit.get_tools()

        # Extract only query_checker (validation)
        query_checker = next(
            (t for t in all_tools if t.name == "sql_db_query_checker"),
            None
        )

        # Custom execution tool via SQLiteService
        @tool
        def execute_sql_query(sql: str) -> str:
            """Execute SQL query on database."""
            return "Tool executed via bind_tools"

        tools = [execute_sql_query]
        if query_checker:
            tools.append(query_checker)

        return tools

    async def _get_system_prompt(self) -> str:
        """Build system prompt: base (from DB) + static rule template."""
        db_record = self.sqlite_service.db_repository.get_current_database()

        if not db_record or not db_record.sql_agent_prompt:
            raise ValueError("SQL agent prompt not generated. Generate prompt first via /generate-prompt endpoint.")

        base_prompt = db_record.sql_agent_prompt  # Dynamic schema from prompt_generator_service

        # Add workflow instructions from prompt template
        enhanced_prompt = f"{base_prompt}\n\n{SQL_AGENT_ENHANCED_PROMPT.format(max_sql_queries=self.max_sql_queries)}"

        return enhanced_prompt
