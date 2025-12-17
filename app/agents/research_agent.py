"""
Research Agent
Stateless LangChain agent for web research using Google Custom Search.
"""
import asyncio
from typing import List, Dict
from langchain_openai import ChatOpenAI

from app.services.llm_service import LLMService
from app.services.google_search_service import GoogleSearchService
from app.schemas.research import ResearchResponse, ResearchReference, AgentStep, AnswerWithCitations
from app.prompts.prompt_manager import RESEARCH_ANSWER_SYNTHESIS_PROMPT, RESEARCH_QUERY_PLANNING_PROMPT


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
        """Perform web research with parallel search execution."""
        self.search_count = 0
        self.reference_counter = 0
        self.all_references = []
        self.max_searches = max_searches

        steps = []

        # Step 1: Query Planning
        search_queries = await self._plan_searches(user_query, max_searches)
        steps.append(AgentStep(
            step_number=len(steps) + 1,
            action="plan_searches",
            action_input=f"Planning {max_searches} search queries",
            observation=f"Planned queries: {', '.join(search_queries)}"
        ))

        # Step2 2: Parallel Search Execution
        search_results = await self._execute_searches_parallel(search_queries)

        # Track each search in steps
        for query, results in search_results.items():
            if isinstance(results, list) and len(results) > 0:
                observation = f"Found {len(results)} results"
            else:
                observation = "No results found"

            steps.append(AgentStep(
                step_number=len(steps) + 1,
                action="web_search",
                action_input=f"{{'query': '{query}'}}",
                observation=observation
            ))

        # Step 3: Answer Synthesis
        final_answer, cited_ids = await self._synthesize_answer(user_query)

        steps.append(AgentStep(
            step_number=len(steps) + 1,
            action="synthesize_answer",
            action_input="Synthesizing final answer from all search results",
            observation=f"Generated answer with {len(cited_ids) if cited_ids else 0} citations"
        ))

        # Prepare references
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

    async def _plan_searches(self, user_query: str, max_searches: int) -> List[str]:
        """Use LLM to plan all search queries upfront."""
        llm = ChatOpenAI(
            model=self.llm_service.model_name,
            api_key=self.llm_service.api_key,
            temperature=0.3
        )

        planning_prompt = RESEARCH_QUERY_PLANNING_PROMPT.format(
            user_query=user_query,
            max_searches=max_searches
        )

        response = await llm.ainvoke(planning_prompt)

        # Parse queries from response
        lines = response.content.strip().split('\n')
        queries = []
        for line in lines:
            # Remove numbering like "1. " or "- "
            query = line.strip().lstrip('0123456789.- ')
            if query:
                queries.append(query)

        return queries[:max_searches]  # Ensure we don't exceed limit

    async def _execute_searches_parallel(self, queries: List[str]) -> Dict[str, List]:
        """Execute multiple web searches in parallel."""

        # Create async tasks for all searches
        tasks = []
        for query in queries:
            task = self.search_service.search(query, num_results=5)
            tasks.append(task)

        # Execute all searches in parallel
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        search_results = {}
        for i, (query, results) in enumerate(zip(queries, results_list)):
            if isinstance(results, Exception):
                # Handle search errors
                search_results[query] = []
            else:
                search_results[query] = results
                self.search_count += 1

                # Track references
                for result in results:
                    self.reference_counter += 1
                    ref_id = f"ref_{self.reference_counter}"
                    self.all_references.append(ResearchReference(
                        reference_id=ref_id,
                        title=result.title,
                        url=result.url,
                        snippet=result.snippet
                    ))

        return search_results

    async def _synthesize_answer(self, user_query: str) -> str:
        """Synthesize final answer from all search results."""

        if not self.all_references:
            return "No search results found to answer the question."

        # Build references list
        ref_list = "\n".join([
            f"[{ref.reference_id}] Title: {ref.title}\nURL: {ref.url}\nSnippet: {ref.snippet}\n"
            for ref in self.all_references
        ])


        synthesis_prompt = RESEARCH_ANSWER_SYNTHESIS_PROMPT.format(
            query=user_query,
            references=ref_list
        )

        llm = ChatOpenAI(
            model=self.llm_service.model_name,
            api_key=self.llm_service.api_key,
            temperature=0.3
        )
        llm_with_structure = llm.with_structured_output(AnswerWithCitations)
        synthesis_response = await llm_with_structure.ainvoke(synthesis_prompt)

        return synthesis_response.answer, synthesis_response.cited_reference_ids
