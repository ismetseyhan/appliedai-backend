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


# Final prompt template for Text-to-SQL agent workflow
SQL_AGENT_ENHANCED_PROMPT = """
## Available Tools

1. **sql_db_query_checker** - Validates SQL syntax
   - Checks query correctness before execution
   - Suggests corrections for syntax errors

2. **execute_sql_query** - Executes SQL query
   - Returns columns, rows, and row_count
   - Respects user permissions
   - Max {max_sql_queries} queries per request

## Workflow

1. Write SQL based on schema above
2. OPTIONAL: Use sql_db_query_checker to validate
3. Use execute_sql_query to run query
4. If error occurs, analyze and retry with corrected query
5. Return clear natural language answer

## Important Rules
- Maximum {max_sql_queries} SQL queries per request
- Retry queries if errors occur (error messages help fix mistakes)
- Provide clear natural language answer after getting results
- Respect user permissions (some operations may be restricted)
- If a process is interrupted due to an unauthorized operation, inform the user of the reason.
"""


# ============================================================================
# Research Agent Prompt
# ============================================================================

RESEARCH_AGENT_PROMPT = """You are an expert research assistant.

## Available Tools
**web_search** - Search the web for information

## Research Guidelines
1. Formulate targeted search queries
2. Perform multiple searches for comprehensive coverage (max {max_searches})
3. Cross-reference information from multiple sources
4. Synthesize clear, well-structured answers
5. Cite sources when making claims

## Response Format
Provide a clear answer based on search results.
The system will automatically attach source references.
"""


RESEARCH_CITATION_EXTRACTION_PROMPT = """The agent provided this answer to the question "{query}":

"{answer}"

Based on this answer and the available references below, identify which reference_id values were likely used to formulate this answer.

Available References:
{references}

Provide the same answer and list the reference IDs that support this answer."""


RESEARCH_ANSWER_SYNTHESIS_PROMPT = """Based on the search results below, provide a clear natural language answer.

Original Question: {query}

Available References:
{references}

IMPORTANT: In your response, include the reference_id of each source you used to formulate your answer in the cited_reference_ids field.

Provide your answer and list the reference IDs you cited."""


# ============================================================================
# PDF Parsing Template Generation Prompt
# ============================================================================

TEMPLATE_GENERATION_PROMPT = """You will be given raw text extracted from a record-based PDF. The PDF contains repeated records with labeled fields in a "Key: Value" style (values may span multiple lines).

Your task: output ONLY a JSON template describing how to split records and extract fields, and identify the best unique identifier field.

Return ONLY valid JSON. No markdown, no comments, no extra text.

Output JSON MUST be an object with EXACTLY these top-level keys:
- record_start
- id_key
- fields

Schema (rules about required/optional properties):
1) record_start: {{ "pattern": "REGEX", "flags": [..] }}
   - flags is a list containing only: MULTILINE, DOTALL, IGNORECASE, UNICODE

2) id_key: "snake_case_string" OR null

3) fields: array of field objects. Each field object MUST include:
   - key (snake_case)
   - labels (array of 1+ regex prefix strings)
   - flags (list; usually ["MULTILINE"])
   - type ("str" | "int" | "float" | "list")
   - required (true/false)
   - normalize_whitespace (true/false)

   Field object MAY include (ONLY when type="list"):
   - split (string, e.g. ",")
   - item_strip (true)

Rules:
1) record_start.pattern matches the start of each record (usually the first label + an ID/unique token). Use ^ + MULTILINE when appropriate.
2) Each labels entry MUST be a regex prefix matching the full label including ":" and trailing whitespace.
   Example JSON regex string: "^Movie Name:\\\\s*"  (this is JSON; it contains two backslashes)
3) The parser takes a field value as the text AFTER its label until the next field label (or end of record).
4) keys must be snake_case and match semantic meaning (use plural for lists: "genres", "actors", "tags").
5) Infer types: int, float, list (comma-separated), otherwise str.
6) If type="list", include split="," and item_strip=true. Otherwise omit split/item_strip entirely.
7) Set normalize_whitespace=true by default for all fields unless the sample clearly requires preserving line breaks.
8) Choose id_key as the field that best uniquely identifies records:
   - Prefer keys/labels containing "id", "no", "number", "code"
   - Prefer type=int
   - If none exists, set id_key to null
9) Use only flags you truly need (usually ["MULTILINE"]; add IGNORECASE only if casing varies).

Expected output example (illustrative only; your output must match the given sample text):
{{
  "record_start": {{
    "pattern": "^Movie ID:\\\\s*\\\\d+",
    "flags": ["MULTILINE"]
  }},
  "id_key": "movie_id",
  "fields": [
    {{
      "key": "movie_id",
      "labels": ["^Movie ID:\\\\s*"],
      "flags": ["MULTILINE"],
      "type": "int",
      "required": true,
      "normalize_whitespace": true
    }},
    {{
      "key": "movie_name",
      "labels": ["^Movie Name:\\\\s*", "^Title:\\\\s*"],
      "flags": ["MULTILINE"],
      "type": "str",
      "required": true,
      "normalize_whitespace": true
    }},
    {{
      "key": "description",
      "labels": ["^Description:\\\\s*", "^Summary:\\\\s*"],
      "flags": ["MULTILINE"],
      "type": "str",
      "required": true,
      "normalize_whitespace": true
    }},
    {{
      "key": "genres",
      "labels": ["^Genre:\\\\s*", "^Genres:\\\\s*"],
      "flags": ["MULTILINE"],
      "type": "list",
      "required": true,
      "normalize_whitespace": true,
      "split": ",",
      "item_strip": true
    }}
  ]
}}

Sample text:
---BEGIN SAMPLE---
{sample_text}
---END SAMPLE---
"""
