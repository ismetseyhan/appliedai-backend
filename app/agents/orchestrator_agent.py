"""
Orchestrator Agent
LangGraph-based multi-agent coordinator for Text-to-SQL, RAG, and Research agents.
"""
import json
import time
from typing import List, Dict, Any, TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, add_messages

from app.agents.text_to_sql_agent import TextToSQLAgent
from app.agents.rag_agent import RAGAgent
from app.agents.research_agent import ResearchAgent
from app.services.llm_service import LLMService
from app.prompts.prompt_manager import ORCHESTRATOR_SUPERVISOR_PROMPT
from sqlalchemy.orm import Session


class OrchestratorState(TypedDict):
    """LangGraph state schema for orchestrator workflow."""
    messages: Annotated[List[BaseMessage], add_messages]
    query: str
    agents_called: List[str]
    agent_responses: Dict[str, Any]
    final_answer: str
    execution_metadata: Dict[str, Any]


class OrchestratorAgent:
    """Multi-agent orchestrator using LangGraph supervisor pattern."""

    def __init__(
            self,
            llm_service: LLMService,
            sql_agent: TextToSQLAgent,
            research_agent: ResearchAgent,
            rag_agent: Optional[RAGAgent],
            user_id: str,
            db: Session
    ):
        self.llm_service = llm_service
        self.sql_agent = sql_agent
        self.research_agent = research_agent
        self.rag_agent = rag_agent
        self.user_id = user_id
        self.db = db

        self.agents_called: List[str] = []
        self.agent_responses: Dict[str, Any] = {}
        self.start_time: float = 0

    async def query(
            self,
            user_query: str,
            conversation_history: List[Dict[str, str]] = None,
            max_iterations: int = 5
    ) -> Dict[str, Any]:
        """Execute orchestrated query using LangGraph."""
        self.start_time = time.time()
        self.agents_called = []
        self.agent_responses = {}
        self.parallel_executions = 0

        messages = []
        if conversation_history:
            for msg in conversation_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=user_query))

        graph = self._build_graph()

        initial_state: OrchestratorState = {
            "messages": messages,
            "query": user_query,
            "agents_called": [],
            "agent_responses": {},
            "final_answer": "",
            "execution_metadata": {}
        }

        final_state = await graph.ainvoke(initial_state)
        execution_time_ms = int((time.time() - self.start_time) * 1000)

        agent_details = {}
        for agent_name, response_data in final_state["agent_responses"].items():
            agent_details[agent_name] = {
                "agent_name": agent_name,
                "steps": response_data.get("steps", []),
                "execution_time_ms": response_data.get("execution_time_ms", 0),
                "result_summary": response_data.get("result_summary", ""),
                "specific_data": response_data.get("specific_data", {})
            }

        return {
            "final_answer": final_state["final_answer"],
            "agents_called": final_state["agents_called"],
            "mode_used": self._determine_mode(final_state["agents_called"], self.parallel_executions),
            "agent_details": agent_details,
            "execution_time_ms": execution_time_ms
        }

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow with supervisor and tool execution nodes."""
        tools = self._create_agent_tools()

        llm = ChatOpenAI(
            model=self.llm_service.model_name,
            api_key=self.llm_service.api_key,
            temperature=0.0
        )
        llm_with_tools = llm.bind_tools(tools)

        async def supervisor_node(state: OrchestratorState) -> Dict:
            from langchain_core.messages import SystemMessage
            messages = [SystemMessage(content=ORCHESTRATOR_SUPERVISOR_PROMPT)] + state["messages"]
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response]}

        async def tool_node(state: OrchestratorState) -> Dict:
            import asyncio

            last_message = state["messages"][-1]
            if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                return {"messages": []}

            agents_called = list(state["agents_called"])
            agent_responses = dict(state["agent_responses"])

            async def execute_tool(tool_call):
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call.get("id", "unknown")

                try:
                    if tool_name == "call_sql_agent":
                        result = await self._execute_sql_agent(tool_args["query"])
                        return ("sql_agent", result, tool_id, None)
                    elif tool_name == "call_rag_agent":
                        result = await self._execute_rag_agent(tool_args["query"])
                        return ("rag_agent", result, tool_id, None)
                    elif tool_name == "call_research_agent":
                        result = await self._execute_research_agent(tool_args["query"])
                        return ("research_agent", result, tool_id, None)
                    elif tool_name == "get_current_datetime":
                        result = await self._execute_datetime_tool()
                        return ("datetime_tool", result, tool_id, None)
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                        return (tool_name, result, tool_id, None)
                except Exception as e:
                    error_msg = f"Error executing {tool_name}: {str(e)}"
                    print(f"[ORCHESTRATOR ERROR] {error_msg}")
                    import traceback
                    traceback.print_exc()
                    return (tool_name, None, tool_id, error_msg)

            results = await asyncio.gather(*[execute_tool(tc) for tc in last_message.tool_calls])

            if len(last_message.tool_calls) > 1:
                self.parallel_executions += 1

            tool_messages = []
            for agent_name, result, tool_id, error in results:
                if error:
                    tool_messages.append(ToolMessage(
                        content=json.dumps({"error": error}),
                        tool_call_id=tool_id
                    ))
                else:
                    agents_called.append(agent_name)
                    agent_responses[agent_name] = result
                    observation = json.dumps(result["result_summary"]) if "result_summary" in result else json.dumps(
                        result)
                    tool_messages.append(ToolMessage(
                        content=observation,
                        tool_call_id=tool_id
                    ))

            return {
                "messages": tool_messages,
                "agents_called": agents_called,
                "agent_responses": agent_responses
            }

        async def final_node(state: OrchestratorState) -> Dict:
            last_ai_message = None
            for msg in reversed(state["messages"]):
                if isinstance(msg, AIMessage):
                    last_ai_message = msg
                    break
            final_answer = last_ai_message.content if last_ai_message else "No answer generated."
            return {"final_answer": final_answer}

        workflow = StateGraph(OrchestratorState)
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("tools", tool_node)
        workflow.add_node("final", final_node)
        workflow.set_entry_point("supervisor")

        def should_continue(state: OrchestratorState) -> str:
            last_message = state["messages"][-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            return "final"

        workflow.add_conditional_edges("supervisor", should_continue, {"tools": "tools", "final": "final"})
        workflow.add_edge("tools", "supervisor")
        workflow.add_edge("final", END)

        return workflow.compile()

    def _create_agent_tools(self) -> List:
        """Create LangChain tools for each agent."""

        @tool
        async def call_sql_agent(query: str) -> str:
            """Query the SQLite movie database using Text-to-SQL agent.

            Use this for:
            - Numerical queries (ratings, budgets, counts)
            - Filtering by attributes (release year, studio, language)
            - Aggregations and comparisons
            - Structured data queries
            """
            return "Tool executed via bind_tools"

        @tool
        async def call_rag_agent(query: str) -> str:
            """Search movie plots and descriptions using semantic search.

            Use this for:
            - Plot summaries and descriptions
            - Theme-based searches
            - Content-based questions
            - Finding movies by plot elements
            """
            return "Tool executed via bind_tools"

        @tool
        async def call_research_agent(query: str) -> str:
            """Search the web for movie-related information.

            Use this for:
            - Production details (producers, directors)
            - Awards and accolades
            - Real-world context and trivia
            - People and crew information
            - Any research on internet
            """
            return "Tool executed via bind_tools"

        @tool
        async def get_current_datetime() -> str:
            """Get current date and time.

            Use this for:
            - Questions about current date or time
            - Calculating time differences or age
            - Determining current year, month, day
            - Time-based context for queries
            """
            return "Tool executed via bind_tools"

        return [call_sql_agent, call_rag_agent, call_research_agent, get_current_datetime]

    async def _execute_sql_agent(self, query: str) -> Dict[str, Any]:
        """Execute Text-to-SQL agent."""
        agent_start = time.time()

        try:
            response = await self.sql_agent.query(query, max_sql_queries=3)

            execution_time_ms = int((time.time() - agent_start) * 1000)

            return {
                "result_summary": response.final_answer,
                "execution_time_ms": execution_time_ms,
                "steps": [s.model_dump() for s in response.steps],
                "specific_data": {
                    "sql_queries": response.sql_queries,
                    "results": response.results
                }
            }
        except Exception as e:
            print(f"[SQL AGENT ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "result_summary": f"SQL Agent error: {str(e)}",
                "execution_time_ms": int((time.time() - agent_start) * 1000),
                "steps": [],
                "specific_data": {"error": str(e)}
            }

    async def _execute_rag_agent(self, query: str) -> Dict[str, Any]:
        """Execute RAG agent."""
        agent_start = time.time()

        if not self.rag_agent:
            return {
                "result_summary": "No RAG data source available. Please configure a document first.",
                "execution_time_ms": 0,
                "steps": [],
                "specific_data": {}
            }

        try:
            response = await self.rag_agent.query(query, top_k=5)
            execution_time_ms = int((time.time() - agent_start) * 1000)

            return {
                "result_summary": response.final_answer,
                "execution_time_ms": execution_time_ms,
                "steps": [s.model_dump() for s in response.steps],
                "specific_data": {
                    "chunks": [c.model_dump() for c in response.chunks],
                    "mode_used": response.mode_used,
                    "filters_applied": response.filters_applied
                }
            }
        except Exception as e:
            print(f"[RAG AGENT ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "result_summary": f"RAG Agent error: {str(e)}",
                "execution_time_ms": int((time.time() - agent_start) * 1000),
                "steps": [],
                "specific_data": {"error": str(e)}
            }

    async def _execute_research_agent(self, query: str) -> Dict[str, Any]:
        """Execute Research agent."""
        agent_start = time.time()

        try:
            response = await self.research_agent.query(query)

            execution_time_ms = int((time.time() - agent_start) * 1000)

            return {
                "result_summary": response.final_answer,
                "execution_time_ms": execution_time_ms,
                "steps": [s.model_dump() for s in response.steps],
                "specific_data": {
                    "references": [r.model_dump() for r in response.references]
                }
            }
        except Exception as e:
            print(f"[RESEARCH AGENT ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "result_summary": f"Research Agent error: {str(e)}",
                "execution_time_ms": int((time.time() - agent_start) * 1000),
                "steps": [],
                "specific_data": {"error": str(e)}
            }

    async def _execute_datetime_tool(self) -> Dict[str, Any]:
        """Execute datetime tool to get current date and time."""
        from datetime import datetime
        import pytz

        agent_start = time.time()

        try:
            utc_now = datetime.now(pytz.UTC)
            local_now = datetime.now()

            result_text = f"""Current Date and Time:
- UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}
- Local: {local_now.strftime('%Y-%m-%d %H:%M:%S')}
- Year: {local_now.year}
- Month: {local_now.strftime('%B')} ({local_now.month})
- Day: {local_now.day}
- Weekday: {local_now.strftime('%A')}
- Time: {local_now.strftime('%H:%M:%S')}"""

            execution_time_ms = int((time.time() - agent_start) * 1000)

            return {
                "result_summary": result_text,
                "execution_time_ms": execution_time_ms,
                "steps": [],
                "specific_data": {
                    "utc": utc_now.isoformat(),
                    "local": local_now.isoformat(),
                    "year": local_now.year,
                    "month": local_now.month,
                    "day": local_now.day,
                    "weekday": local_now.strftime('%A'),
                    "formatted": local_now.strftime('%Y-%m-%d %H:%M:%S')
                }
            }
        except Exception as e:
            print(f"[DATETIME TOOL ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "result_summary": f"Datetime tool error: {str(e)}",
                "execution_time_ms": int((time.time() - agent_start) * 1000),
                "steps": [],
                "specific_data": {"error": str(e)}
            }

    def _determine_mode(self, agents_called: List[str], parallel_count: int) -> str:
        """Determine execution mode based on agents called and parallel execution count."""
        if len(agents_called) == 0:
            return "none"
        elif len(agents_called) == 1:
            return "single"
        elif parallel_count > 0:
            # At least one batch of parallel execution occurred
            return "parallel"
        else:
            # Multiple agents, but all executed sequentially
            return "sequential"
