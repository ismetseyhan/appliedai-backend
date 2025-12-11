"""
Research Agent
Stateless LangChain agent for web research using Google Custom Search.
"""
import json
from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.services.llm_service import LLMService
from app.services.google_search_service import GoogleSearchService
from app.schemas.research import ResearchResponse, ResearchReference, AgentStep, AnswerWithCitations
from app.prompts.prompt_manager import (
    RESEARCH_AGENT_PROMPT,
    RESEARCH_CITATION_EXTRACTION_PROMPT,
    RESEARCH_ANSWER_SYNTHESIS_PROMPT
)


class ResearchAgent:

    def __init__(
        self,
        llm_service: LLMService,
        search_service: GoogleSearchService,
        user_id: str
    ):
        self.llm_service = llm_service
        self.search_service = search_service
        self.user_id = user_id
        self.search_count = 0
        self.reference_counter = 0
        self.all_references = []

    async def query(self, user_query: str, max_searches: int = 3) -> ResearchResponse:
        """Perform web research and return synthesized answer with references."""
        self.search_count = 0
        self.reference_counter = 0
        self.all_references = []
        self.max_searches = max_searches

        llm = ChatOpenAI(
            model=self.llm_service.model_name,
            api_key=self.llm_service.api_key,
            temperature=0.3
        )

        tools = self._get_tools()
        llm_with_tools = llm.bind_tools(tools)

        system_prompt = RESEARCH_AGENT_PROMPT.format(max_searches=max_searches)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("placeholder", "{messages}")
        ])

        chain = prompt | llm_with_tools

        steps = []
        iteration = 0
        max_iterations = 10
        final_answer = None

        messages = [HumanMessage(content=user_query)]

        while iteration < max_iterations:
            iteration += 1

            response = await chain.ainvoke({"messages": messages})

            if not response.tool_calls:
                final_answer = response.content
                break

            messages.append(response)

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]

                if tool_name == "web_search":
                    query = tool_call["args"]["query"]

                    if self.search_count >= self.max_searches:
                        observation = json.dumps({"error": f"Maximum search limit ({self.max_searches}) reached"})

                    else:
                        try:
                            results = self.search_service.search(query, num_results=5)
                            self.search_count += 1

                            for result in results:
                                self.reference_counter += 1
                                ref_id = f"ref_{self.reference_counter}"

                                self.all_references.append(ResearchReference(
                                    reference_id=ref_id,
                                    title=result.title,
                                    url=result.url,
                                    snippet=result.snippet
                                ))

                            results_dict = [
                                {
                                    "reference_id": r.reference_id,
                                    "title": r.title,
                                    "url": r.url,
                                    "snippet": r.snippet
                                }
                                for r in self.all_references[-len(results):]
                            ]
                            observation = json.dumps({"results": results_dict})
                        except Exception as e:
                            observation = json.dumps({"error": str(e)})

                else:
                    observation = json.dumps({"error": f"Unknown tool: {tool_name}"})

                messages.append(ToolMessage(
                    content=observation,
                    tool_call_id=tool_call.get("id", "unknown")
                ))

                steps.append(AgentStep(
                    step_number=len(steps) + 1,
                    action=tool_name,
                    action_input=str(tool_call["args"]),
                    observation=observation[:500]
                ))

        if self.search_count > 0:
            ref_list = "\n".join([
                f"[{ref.reference_id}] Title: {ref.title}\nURL: {ref.url}\nSnippet: {ref.snippet}\n"
                for ref in self.all_references
            ])

            if final_answer:
                synthesis_prompt = RESEARCH_CITATION_EXTRACTION_PROMPT.format(
                    query=user_query,
                    answer=final_answer,
                    references=ref_list
                )
            else:
                synthesis_prompt = RESEARCH_ANSWER_SYNTHESIS_PROMPT.format(
                    query=user_query,
                    references=ref_list
                )

            llm_with_structure = llm.with_structured_output(AnswerWithCitations)
            synthesis_response = await llm_with_structure.ainvoke(synthesis_prompt)

            if not final_answer:
                final_answer = synthesis_response.answer

            cited_ids = synthesis_response.cited_reference_ids
        else:
            cited_ids = None

        if not final_answer:
            final_answer = "Could not generate answer within iteration limit"

        if cited_ids:
            ref_map = {ref.reference_id: ref for ref in self.all_references}
            references = [ref_map[ref_id] for ref_id in cited_ids if ref_id in ref_map]
        else:
            unique_refs = {ref.url: ref for ref in self.all_references}
            references = list(unique_refs.values())[:10]

        return ResearchResponse(
            query=user_query,
            final_answer=final_answer,
            references=references,
            steps=steps,
            execution_time_ms=0
        )

    def _get_tools(self) -> List:
        @tool
        def web_search(query: str) -> str:
            return "Tool executed via bind_tools"

        return [web_search]
