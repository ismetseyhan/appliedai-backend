"""
Prompt Generator Service
Generates Text-to-SQL agent system prompts using LLM.
Analyzes database schema, relationships, data statistics, and examples.
"""

from typing import Dict, List, Any
from pathlib import Path
import sqlite3
from app.services.llm_service import LLMService
from app.prompts import SQL_AGENT_META_PROMPT


class PromptGeneratorService:
    """
    Service for generating Text-to-SQL agent prompts dynamically.
    Workflow:
    1. Extract database metadata (schema, FKs, stats, samples)
    2. Build meta-prompt for LLM
    3. Call LLM to generate optimized Text-to-SQL system prompt
    4. Return final prompt for storage
    """

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def generate_prompt(
        self,
        db_path: Path,
        db_name: str,
        allowed_operations: List[str]
    ) -> str:
        """Generate Text-to-SQL prompt for a database using LLM"""
        context = self._extract_database_context(db_path)

        meta_prompt = self._build_meta_prompt(
            db_name=db_name,
            context=context,
            allowed_operations=allowed_operations
        )

        final_prompt = await self._generate_with_llm(meta_prompt)

        return final_prompt

    def _extract_database_context(self, db_path: Path) -> Dict[str, Any]:
        """
        Extract comprehensive database metadata including schema, relationships, samples, and statistics.

        Returns dict with "tables" (list of table info) and "relationships" (list of FK descriptions)
        """
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        context = {
            "tables": [],
            "relationships": []
        }

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        for table_name in tables:
            table_info = self._extract_table_info(cursor, table_name)
            context["tables"].append(table_info)

        # Extract relationships
        context["relationships"] = self._extract_relationships(context["tables"])

        conn.close()
        return context

    def _extract_table_info(self, cursor, table_name: str) -> Dict[str, Any]:
        """Extract detailed info for a single table (columns, FKs, row count, samples, statistics)"""
        # Get columns with PK info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_raw = cursor.fetchall()
        columns = [
            {
                "name": col[1],
                "type": col[2],
                "is_pk": bool(col[5])
            }
            for col in columns_raw
        ]

        # Get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        fks_raw = cursor.fetchall()
        foreign_keys = [
            {
                "column": fk[3],
                "references": f"{fk[2]}.{fk[4]}"
            }
            for fk in fks_raw
        ]

        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]

        # Get sample rows (3 rows)
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        sample_rows = [dict(row) for row in cursor.fetchall()]

        # Get statistics for categorical/numeric columns
        statistics = self._calculate_column_statistics(cursor, table_name, columns)

        return {
            "name": table_name,
            "row_count": row_count,
            "columns": columns,
            "foreign_keys": foreign_keys,
            "sample_rows": sample_rows,
            "statistics": statistics
        }

    def _calculate_column_statistics(
        self,
        cursor,
        table_name: str,
        columns: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate column statistics (distinct counts, min/max, common values for categorical/numeric columns)"""
        stats = {}

        for col in columns:
            col_name = col["name"]
            col_type = col["type"].upper()

            # For categorical columns (VARCHAR, TEXT)
            if "VARCHAR" in col_type or "TEXT" in col_type:
                # Get distinct count
                cursor.execute(f"SELECT COUNT(DISTINCT {col_name}) FROM {table_name}")
                distinct_count = cursor.fetchone()[0]

                # Get top 5 common values (if distinct count < 20, likely categorical)
                if distinct_count < 20:
                    cursor.execute(f"""
                        SELECT {col_name}, COUNT(*) as cnt
                        FROM {table_name}
                        GROUP BY {col_name}
                        ORDER BY cnt DESC
                        LIMIT 5
                    """)
                    common_values = [row[0] for row in cursor.fetchall()]

                    stats[col_name] = {
                        "distinct_count": distinct_count,
                        "common_values": common_values
                    }

            # For numeric columns (INT, FLOAT, REAL)
            elif any(t in col_type for t in ["INT", "FLOAT", "REAL", "NUMERIC"]):
                cursor.execute(f"""
                    SELECT
                        MIN({col_name}),
                        MAX({col_name}),
                        AVG({col_name})
                    FROM {table_name}
                """)
                min_val, max_val, avg_val = cursor.fetchone()

                stats[col_name] = {
                    "min": min_val,
                    "max": max_val,
                    "avg": round(avg_val, 2) if avg_val else None
                }

        return stats

    def _extract_relationships(self, tables: List[Dict]) -> List[str]:
        """Build human-readable relationship descriptions from foreign keys"""
        relationships = []

        for table in tables:
            for fk in table["foreign_keys"]:
                rel_desc = f"{table['name']}.{fk['column']} → {fk['references']} (Many-to-One)"
                relationships.append(rel_desc)

        # Detect many-to-many
        for table in tables:
            if len(table["foreign_keys"]) == 2 and len(table["columns"]) == 2:
                # Likely junction table
                fk1 = table["foreign_keys"][0]
                fk2 = table["foreign_keys"][1]
                ref_table1 = fk1["references"].split(".")[0]
                ref_table2 = fk2["references"].split(".")[0]

                rel_desc = f"{ref_table1} ↔ {ref_table2} via {table['name']} (Many-to-Many)"
                relationships.append(rel_desc)

        return relationships

    def _build_meta_prompt(
        self,
        db_name: str,
        context: Dict[str, Any],
        allowed_operations: List[str]
    ) -> str:
        """Build meta-prompt asking LLM to generate optimized Text-to-SQL system prompt"""
        schema_text = self._format_schema(context["tables"])
        relationships_text = "\n".join(context["relationships"])
        samples_text = self._format_sample_data(context["tables"])
        stats_text = self._format_statistics(context["tables"])

        meta_prompt = SQL_AGENT_META_PROMPT.format(
            db_name=db_name,
            allowed_operations=", ".join(allowed_operations),
            schema_text=schema_text,
            relationships_text=relationships_text,
            samples_text=samples_text,
            stats_text=stats_text
        )

        return meta_prompt

    def _format_schema(self, tables: List[Dict]) -> str:
        """Format schema information for meta-prompt"""
        lines = []
        for table in tables:
            lines.append(f"\nTable: {table['name']} ({table['row_count']} rows)")
            for col in table["columns"]:
                pk_marker = " [PRIMARY KEY]" if col["is_pk"] else ""
                lines.append(f"  - {col['name']}: {col['type']}{pk_marker}")

            if table["foreign_keys"]:
                lines.append("  Foreign Keys:")
                for fk in table["foreign_keys"]:
                    lines.append(f"    - {fk['column']} → {fk['references']}")

        return "\n".join(lines)

    def _format_sample_data(self, tables: List[Dict]) -> str:
        """Format sample data for meta-prompt"""
        lines = []
        for table in tables:
            lines.append(f"\n{table['name']}:")
            for i, row in enumerate(table["sample_rows"][:3], 1):
                lines.append(f"  Row {i}: {row}")

        return "\n".join(lines)

    def _format_statistics(self, tables: List[Dict]) -> str:
        """Format column statistics for meta-prompt"""
        lines = []
        for table in tables:
            if table["statistics"]:
                lines.append(f"\n{table['name']}:")
                for col_name, stats in table["statistics"].items():
                    if "common_values" in stats:
                        lines.append(f"  - {col_name}: {stats['distinct_count']} distinct values")
                        lines.append(f"    Common: {', '.join(map(str, stats['common_values']))}")
                    elif "min" in stats:
                        lines.append(f"  - {col_name}: range [{stats['min']} - {stats['max']}], avg: {stats['avg']}")

        return "\n".join(lines)

    async def _generate_with_llm(self, meta_prompt: str) -> str:
        """Call LLM to generate the final Text-to-SQL prompt"""
        messages = [
            {"role": "user", "content": meta_prompt}
        ]

        prompt = await self.llm.achat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=2000
        )

        return prompt.strip()
