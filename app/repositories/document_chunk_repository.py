from typing import List, Optional, Any, Tuple, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Integer, String, text
from app.entities.document_chunk import DocumentChunk


class DocumentChunkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, chunk: DocumentChunk) -> DocumentChunk:
        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    def bulk_create(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        self.db.add_all(chunks)
        self.db.flush()
        self.db.commit()
        return chunks

    def get_by_document_chunking_id(self, document_chunking_id: str, limit: Optional[int] = None) -> List[DocumentChunk]:
        """Get chunks by chunking ID, optionally limited."""
        query = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        ).order_by(DocumentChunk.record_index)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        return self.db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()

    def delete_by_document_chunking_id(self, document_chunking_id: str) -> int:
        count = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        ).delete()
        self.db.commit()
        return count

    def count_by_document_chunking_id(self, document_chunking_id: str) -> int:
        return self.db.query(DocumentChunk).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        ).count()

    def semantic_search(
        self,
        query_embedding: List[float],
        document_chunking_id: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """Semantic search using pgvector cosine distance."""
        query = self.db.query(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(query_embedding).label('distance')
        ).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        )

        if metadata_filter:
            query = self._apply_metadata_filters(query, metadata_filter)

        results = query.order_by('distance').limit(top_k).all()
        return [(chunk, 1.0 - distance) for chunk, distance in results]  # Convert to similarity

    def keyword_search(
        self,
        query_text: str,
        document_chunking_id: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """Full-text keyword search using PostgreSQL ts_vector."""
        query = self.db.query(
            DocumentChunk,
            func.ts_rank(
                func.to_tsvector('english', DocumentChunk.llm_text),
                func.plainto_tsquery('english', query_text)
            ).label('rank')
        ).filter(
            DocumentChunk.document_chunking_id == document_chunking_id,
            func.to_tsvector('english', DocumentChunk.llm_text).op('@@')(
                func.plainto_tsquery('english', query_text)
            )
        )

        if metadata_filter:
            query = self._apply_metadata_filters(query, metadata_filter)

        results = query.order_by(text('rank DESC')).limit(top_k).all()
        return [(chunk, float(rank)) for chunk, rank in results]

    def hybrid_search(
        self,
        query_embedding: List[float],
        query_text: str,
        document_chunking_id: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
        semantic_weight: float = 0.5
    ) -> List[Tuple[DocumentChunk, float]]:
        """Hybrid search using RRF (k=60): score = sum(1 / (60 + rank_i))."""
        semantic_results = self.semantic_search(
            query_embedding, document_chunking_id, top_k * 2, metadata_filter
        )
        keyword_results = self.keyword_search(
            query_text, document_chunking_id, top_k * 2, metadata_filter
        )

        k = 60
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, DocumentChunk] = {}

        for rank, (chunk, _) in enumerate(semantic_results, 1):
            chunk_id = chunk.id
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + (1 / (k + rank)) * semantic_weight
            chunk_map[chunk_id] = chunk

        for rank, (chunk, _) in enumerate(keyword_results, 1):
            chunk_id = chunk.id
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + (1 / (k + rank)) * (1 - semantic_weight)
            chunk_map[chunk_id] = chunk

        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(chunk_map[chunk_id], score) for chunk_id, score in sorted_results]

    def find_neighbors(
        self,
        seed_chunk: DocumentChunk,
        document_chunking_id: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """Find similar chunks based on seed embedding (excludes seed itself)."""
        if seed_chunk.embedding is None:
            raise ValueError("Seed chunk has no embedding")

        query = self.db.query(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(seed_chunk.embedding).label('distance')
        ).filter(
            DocumentChunk.document_chunking_id == document_chunking_id,
            DocumentChunk.id != seed_chunk.id
        )

        if metadata_filter:
            query = self._apply_metadata_filters(query, metadata_filter)

        results = query.order_by('distance').limit(top_k).all()
        return [(chunk, 1.0 - distance) for chunk, distance in results]

    def get_by_metadata_filter(
        self,
        metadata_filter: Dict[str, Any],
        document_chunking_id: str
    ) -> Optional[DocumentChunk]:
        """Single-record lookup using metadata filter."""
        query = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_chunking_id == document_chunking_id
        )

        if metadata_filter:
            query = self._apply_metadata_filters(query, metadata_filter)

        return query.first()

    def _apply_metadata_filters(
        self,
        query,
        metadata_filter: Dict[str, Any]
    ) -> Any:
        """Apply JSONB metadata filters dynamically."""
        if not metadata_filter or 'and' not in metadata_filter:
            return query

        for condition in metadata_filter['and']:
            field = condition['field']
            field_type = condition['type']
            operator = condition['op']
            value = condition['value']

            if field_type == 'list':
                if operator == 'contains':
                    query = query.filter(
                        DocumentChunk.chunk_metadata[field].astext.contains(f'"{value}"')
                    )
                elif operator == 'in_list':
                    for v in value:
                        query = query.filter(
                            DocumentChunk.chunk_metadata[field].astext.contains(f'"{v}"')
                        )

            elif field_type == 'int':
                cast_expr = DocumentChunk.chunk_metadata[field].astext.cast(Integer)
                if operator == 'equals':
                    query = query.filter(cast_expr == value)
                elif operator == 'greater_than':
                    query = query.filter(cast_expr > value)
                elif operator == 'less_than':
                    query = query.filter(cast_expr < value)
                elif operator == 'between':  # value = [min, max]
                    query = query.filter(cast_expr.between(value[0], value[1]))

            elif field_type == 'str':
                if operator == 'equals':
                    query = query.filter(
                        func.lower(DocumentChunk.chunk_metadata[field].astext) == value.lower()
                    )

        return query

    def get_metadata_statistics(
        self,
        document_chunking_id: str,
        numeric_fields: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate min/max statistics for numeric metadata fields."""
        stats = {}

        for field in numeric_fields:
            result = self.db.query(
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

        return stats
