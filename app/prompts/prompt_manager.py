# ============================================================================
# Text to SQL Dynamic Prompt Generator
# ============================================================================

SQL_AGENT_META_PROMPT = """You are a prompt engineering expert specializing in Text-to-SQL systems.

Your task: Generate the BEST POSSIBLE system prompt for a Text-to-SQL AI agent that will write SQLite queries for the database described below.

DATABASE NAME: {db_name}

ALLOWED SQL OPERATIONS: {allowed_operations}

DATABASE SCHEMA:
{schema_text}

TABLE RELATIONSHIPS:
{relationships_text}

SAMPLE DATA (3 rows per table):
{samples_text}

DATA STATISTICS:
{stats_text}

REQUIREMENTS FOR THE PROMPT YOU GENERATE:
1. The prompt should instruct the AI agent on how to write correct SQLite queries
2. Include specific information about table names, column names, data types
3. Explain the relationships between tables (foreign keys, join paths)
4. Mention value constraints (e.g., valid industry values, year ranges)
5. Provide guidance on common query patterns for this database
6. Emphasize syntactic correctness and SQLite-specific features
7. Remind the agent to use table aliases and proper JOINs
8. Include warnings about case-sensitive column names
9. The prompt should be clear, comprehensive, and actionable

IMPORTANT: Generate ONLY the system prompt text. Do NOT include explanations, meta-commentary, or markdown formatting. Just the raw prompt text that will be used as the Text-to-SQL agent's system message.

Generate the optimal Text-to-SQL agent system prompt now:"""
