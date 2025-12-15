"""
RAG Agent
Stateless langchain retrieval-augmented generation .
"""
import json
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.llm_service import LLMService
from app.schemas.rag import RAGResponse, RetrievedChunk, AgentStep


class RAGAgent:
    """RAG Agent with retrieve_records and get_record tools."""

    def __init__(
        self,
        chunk_repository: DocumentChunkRepository,
        llm_service: LLMService,
        document_chunking_id: str,
        agent_prompt: str
    ):
        self.chunk_repository = chunk_repository
        self.llm_service = llm_service
        self.document_chunking_id = document_chunking_id
        self.agent_prompt = agent_prompt
        self.retrieved_chunks: List[RetrievedChunk] = []
        self.mode_used: str = ""
        self.filters_applied: bool = False

    async def query(self, user_query: str, top_k: int = 5) -> RAGResponse:
        """Execute RAG query with multi-turn retry logic."""
        self.retrieved_chunks = []
        self.mode_used = ""
        self.filters_applied = False

        llm = ChatOpenAI(
            model=self.llm_service.model_name,
            api_key=self.llm_service.api_key,
            temperature=0.3
        )

        tools = self._get_tools()
        llm_with_tools = llm.bind_tools(tools)
        system_prompt = self._get_system_prompt(top_k)

        steps = []
        final_answer = None

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_query)
        ]

        # Retry loop: max 3 iterations
        iteration = 0
        max_iterations = 3

        while iteration < max_iterations:
            iteration += 1

            response = await llm_with_tools.ainvoke(messages)

            if not response.tool_calls:
                final_answer = response.content
                break

            messages.append(response)

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                if tool_name == "retrieve_records":
                    observation = await self._execute_retrieve_records(tool_args)
                elif tool_name == "get_record":
                    observation = await self._execute_get_record(tool_args)
                else:
                    observation = json.dumps({"error": f"Unknown tool: {tool_name}"})

                messages.append(ToolMessage(
                    content=observation,
                    tool_call_id=tool_call.get("id", "unknown")
                ))

                steps.append(AgentStep(
                    step_number=len(steps) + 1,
                    action=tool_name,
                    action_input=str(tool_args),
                    observation=observation[:500]
                ))

            if self.retrieved_chunks:
                break

        if self.retrieved_chunks:
            from app.prompts.prompt_manager import RAG_ANSWER_SYNTHESIS_PROMPT

            synthesis_prompt = RAG_ANSWER_SYNTHESIS_PROMPT.format(
                user_query=user_query,
                chunks=self._format_chunks_for_synthesis()
            )

            final_response = await llm.ainvoke(synthesis_prompt)
            final_answer = final_response.content
        else:
            final_answer = "No relevant records found for your query after trying multiple retrieval strategies."

        return RAGResponse(
            query=user_query,
            final_answer=final_answer,
            chunks=self.retrieved_chunks,
            mode_used=self.mode_used,
            filters_applied=self.filters_applied,
            steps=steps,
            execution_time_ms=0
        )

    async def _execute_retrieve_records(self, args: Dict[str, Any]) -> str:
        """Execute retrieve_records tool."""
        query_text = args.get("query", "")
        top_k = args.get("top_k", 5)
        mode = args.get("mode", "semantic")
        metadata_filter = args.get("metadata_filter")
        seed = args.get("seed")

        self.mode_used = mode
        self.filters_applied = metadata_filter is not None

        try:
            query_embedding = None
            if mode in ["semantic", "hybrid"]:
                query_embedding = await self.llm_service.create_embedding(query_text)

            if mode == "semantic":
                results = self.chunk_repository.semantic_search(
                    query_embedding, self.document_chunking_id, top_k, metadata_filter
                )
            elif mode == "keyword":
                results = self.chunk_repository.keyword_search(
                    query_text, self.document_chunking_id, top_k, metadata_filter
                )
            elif mode == "hybrid":
                results = self.chunk_repository.hybrid_search(
                    query_embedding, query_text, self.document_chunking_id, top_k, metadata_filter
                )
            elif mode == "neighbors":
                seed_chunk = None
                if seed:
                    if "id" in seed:
                        seed_chunk = self.chunk_repository.get_by_id(seed["id"])
                    elif "and" in seed:
                        seed_chunk = self.chunk_repository.get_by_metadata_filter(
                            seed, self.document_chunking_id
                        )
                    else:
                        return json.dumps({
                            "error": "Invalid seed format. Use metadata_filter format or {'id': 'chunk-uuid'}"
                        })

                if not seed_chunk:
                    return json.dumps({"error": "Seed record not found"})

                results = self.chunk_repository.find_neighbors(
                    seed_chunk, self.document_chunking_id, top_k, metadata_filter
                )
            else:
                return json.dumps({"error": f"Invalid mode: {mode}"})

            self.retrieved_chunks = [
                RetrievedChunk(
                    id=chunk.id,
                    score=round(score, 4),
                    llm_text=chunk.llm_text or "",
                    metadata=chunk.chunk_metadata or {}
                )
                for chunk, score in results
            ]

            return json.dumps({
                "results": [
                    {
                        "id": c.id,
                        "score": c.score,
                        "llm_text": c.llm_text[:200] + "..." if len(c.llm_text) > 200 else c.llm_text,
                        "metadata": c.metadata
                    }
                    for c in self.retrieved_chunks
                ],
                "mode_used": mode,
                "filters_applied": self.filters_applied,
                "count": len(self.retrieved_chunks)
            })

        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _execute_get_record(self, args: Dict[str, Any]) -> str:
        """Execute get_record tool."""
        try:
            metadata_filter = args.get("metadata_filter")
            if not metadata_filter:
                return json.dumps({"error": "metadata_filter is required"})

            chunk = self.chunk_repository.get_by_metadata_filter(
                metadata_filter, self.document_chunking_id
            )

            if not chunk:
                return json.dumps({"error": "Record not found"})

            retrieved = RetrievedChunk(
                id=chunk.id,
                score=1.0,
                llm_text=chunk.llm_text or "",
                metadata=chunk.chunk_metadata or {}
            )

            self.retrieved_chunks = [retrieved]
            self.mode_used = "direct_lookup"

            return json.dumps({
                "llm_text": retrieved.llm_text,
                "metadata": retrieved.metadata
            })

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _get_tools(self) -> List:
        """Define LangChain tools."""

        @tool
        def retrieve_records(
            query: str,
            top_k: int = 5,
            mode: str = "semantic",
            metadata_filter: Optional[Dict] = None,
            seed: Optional[Dict] = None
        ) -> str:
            """Retrieve records using semantic/keyword/hybrid/neighbors mode."""
            return "Tool executed via bind_tools"

        @tool
        def get_record(metadata_filter: Dict) -> str:
            """Get specific record by metadata filter."""
            return "Tool executed via bind_tools"

        return [retrieve_records, get_record]

    def _get_system_prompt(self, top_k: int) -> str:
        """Build system prompt (dynamic base + static enhanced)."""
        from app.prompts.prompt_manager import RAG_AGENT_ENHANCED_PROMPT
        return self.agent_prompt + "\n\n" + RAG_AGENT_ENHANCED_PROMPT.format(top_k=top_k)

    def _format_chunks_for_synthesis(self) -> str:
        """Format chunks for LLM synthesis."""
        formatted = []
        for i, chunk in enumerate(self.retrieved_chunks, 1):
            formatted.append(f"[Chunk {i}] (Score: {chunk.score})")
            formatted.append(f"Text: {chunk.llm_text}")
            formatted.append(f"Metadata: {json.dumps(chunk.metadata)}")
            formatted.append("")
        return "\n".join(formatted)
