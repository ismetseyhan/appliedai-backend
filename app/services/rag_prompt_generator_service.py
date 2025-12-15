from typing import Dict, List, Any
import json
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer
from app.entities.document_chunk import DocumentChunk
from app.entities.document_chunking import DocumentChunking
from app.services.llm_service import LLMService


class RagPromptGeneratorService:
    """Generate RAG agent prompts by analyzing document chunks."""

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def generate_prompt(
        self,
        document_chunking_id: str,
        db: Session
    ) -> str:
        """Generate RAG agent prompt for a chunking step."""
        context = self._extract_chunk_context(document_chunking_id, db)
        meta_prompt = self._build_meta_prompt(context)
        final_prompt = await self._generate_with_llm(meta_prompt)
        return final_prompt

    def _extract_chunk_context(self, document_chunking_id: str, db: Session) -> Dict:
        """Extract metadata schema, samples, and statistics from chunks."""
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        ).order_by(DocumentChunk.record_index).limit(10).all()

        if not chunks:
            raise ValueError("No chunks found for this configuration")

        total_chunks = db.query(func.count(DocumentChunk.id)).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        ).scalar()

        doc_chunking = db.query(DocumentChunking).filter(
            DocumentChunking.id == document_chunking_id
        ).first()

        sample_records = self._format_sample_records(chunks[:2])
        metadata_schema = self._infer_metadata_schema(chunks)  # Infer from 10 chunks
        statistics = self._calculate_statistics(document_chunking_id, metadata_schema, db)

        return {
            "total_chunks": total_chunks,
            "document_name": doc_chunking.document.file_name,
            "chunking_name": doc_chunking.name,
            "sample_records": sample_records,
            "metadata_schema": metadata_schema,
            "statistics": statistics
        }

    def _format_sample_records(self, chunks: List[DocumentChunk]) -> List[Dict]:
        """Format sample chunks (truncate llm_text to 500 chars)."""
        samples = []
        for chunk in chunks:
            llm_text = chunk.llm_text or ""
            if len(llm_text) > 500:
                llm_text = llm_text[:500] + "..."

            samples.append({
                "record_index": chunk.record_index,
                "llm_text": llm_text,
                "metadata": chunk.chunk_metadata or {}  # No embedding - token waste
            })
        return samples

    def _infer_metadata_schema(self, chunks: List[DocumentChunk]) -> Dict:
        """Infer metadata schema with types and examples from chunks."""
        schema = {}

        for chunk in chunks:
            metadata = chunk.chunk_metadata or {}
            for key, value in metadata.items():
                if key not in schema:
                    schema[key] = {
                        "type": self._infer_type(value),
                        "examples": []
                    }

                if len(schema[key]["examples"]) < 5:  # Collect up to 5 examples
                    schema[key]["examples"].append(value)

        return schema

    def _infer_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, list):
            if value and isinstance(value[0], str):
                return "list[str]"
            elif value and isinstance(value[0], int):
                return "list[int]"
            else:
                return "list"
        else:
            return "str"

    def _calculate_statistics(
        self,
        document_chunking_id: str,
        metadata_schema: Dict,
        db: Session
    ) -> Dict:
        """Calculate min/max for numeric metadata fields."""
        stats = {}

        numeric_fields = [
            key for key, info in metadata_schema.items()
            if info["type"] in ["int", "float"]
        ]

        for field in numeric_fields:
            result = db.query(
                func.min((DocumentChunk.chunk_metadata[field].cast(Integer))).label('min_val'),
                func.max((DocumentChunk.chunk_metadata[field].cast(Integer))).label('max_val')
            ).filter(
                DocumentChunk.document_chunking_id == document_chunking_id
            ).first()

            if result:
                stats[field] = {
                    "min": result.min_val,
                    "max": result.max_val
                }

        return {"numeric_fields": stats}

    def _build_meta_prompt(self, context: Dict) -> str:
        """Build meta-prompt asking LLM to generate RAG agent prompt."""
        from app.prompts.prompt_manager import RAG_AGENT_META_PROMPT

        samples_text = json.dumps(context["sample_records"], indent=2)
        metadata_schema_text = json.dumps(context["metadata_schema"], indent=2)
        stats_text = self._format_statistics(context)

        meta_prompt = RAG_AGENT_META_PROMPT.format(
            total_chunks=context["total_chunks"],
            document_name=context["document_name"],
            chunking_name=context["chunking_name"],
            sample_count=len(context["sample_records"]),
            samples_text=samples_text,
            metadata_schema_text=metadata_schema_text,
            stats_text=stats_text
        )

        return meta_prompt

    def _format_statistics(self, context: Dict) -> str:
        lines = [f"- Total chunks: {context['total_chunks']}"]

        numeric_stats = context["statistics"].get("numeric_fields", {})
        if numeric_stats:
            lines.append("- Numeric fields:")
            for field, stats in numeric_stats.items():
                lines.append(f"  - {field}: min={stats['min']}, max={stats['max']}")

        return "\n".join(lines)

    async def _generate_with_llm(self, meta_prompt: str) -> str:
        """Call LLM to generate the final RAG agent prompt."""
        messages = [
            {"role": "user", "content": meta_prompt}
        ]

        prompt = await self.llm.achat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=2000
        )

        return prompt.strip()
