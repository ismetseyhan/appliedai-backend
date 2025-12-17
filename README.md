# Multi-Agent Movie Intelligence System - Backend

FastAPI backend with AI agents, document processing, and multi-modal data intelligence.

## Overview

This system implements a multi-agent architecture using LangChain and LangGraph to provide intelligent interactions with structured (SQL) and unstructured (document) data, combined with web research capabilities.

**Tech Stack:**
- FastAPI + PostgreSQL (pgvector for embeddings)
- LangChain + LangGraph (agent orchestration)
- OpenAI GPT (gpt-4o for agents, embeddings)
- Firebase Authentication
- Google Custom Search API

**Core Capabilities:**
- Text-to-SQL agent with multi-step reasoning
- RAG agent with 4 retrieval modes (semantic, keyword, hybrid, neighbors)
- Web research agent with citation tracking
- Multi-agent orchestration via LangGraph
- Dynamic prompt generation per dataset
- Document parsing and chunking pipeline

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Setup Environment
```bash
cp .env.example .env
```

Required environment variables:
- **Firebase**: Service account JSON for authentication
- **OpenAI**: `OPENAI_API_KEY` for LLM and embeddings
- **Google Search**: `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` for research agent
- **Database**: PostgreSQL connection string

### 3. Start PostgreSQL (Docker)
```bash
docker-compose up -d
```

Includes pgvector extension for semantic search.

### 4. Run Database Migrations
```bash
# Apply migrations
alembic upgrade head

# Check current version
alembic current
```

### 5. Run Server
```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Test API
- Swagger Docs: https://appliedai-be.ismetseyhan.com/docs
- Health Check: https://appliedai-be.ismetseyhan.com/health
- Local: http://localhost:8000/docs

---

## Architecture & Design

### System Overview

**Backend:** FastAPI + SQLAlchemy ORM
**Frontend:** React 19 + TypeScript
**Database:** PostgreSQL with pgvector extension
**Storage:** Firebase Storage with signed URLs
**AI Layer:** LangChain + LangGraph + OpenAI GPT

### Clean Architecture Pattern

```
HTTP Request
    ↓
API Endpoint (FastAPI router)
    ↓
Service Layer (business logic)
    ├─→ Agent Layer (LangChain/LangGraph) - AI operations
    └─→ Repository Layer (database access) - Data operations
    ↓
Database (PostgreSQL + SQLite)
Storage (Firebase)
```

**Key Principles:**
- **Dependency Injection**: All dependencies via `app/api/deps.py`
- **Separation of Concerns**: Routers handle HTTP, services orchestrate logic, repositories handle data, agents handle AI
- **Stateless Agents**: Conversation history managed in database, not in-memory
- **Type Safety**: Pydantic schemas for all requests/responses

### Agent Integration

All AI agents follow a consistent pattern:
1. **Tool Binding**: Tools defined via `@tool` decorator
2. **Message History**: Within-request conversation for error correction
3. **Multi-Turn Iteration**: Agents can retry and chain operations
4. **Synthesis**: Final answer generation from tool results

---

## AI Agents

### Architecture Overview

All agents are **stateless** - conversation history is managed within a single request, enabling error correction and multi-step reasoning without maintaining session state.

**Common Components:**
- LangChain framework for tool binding
- OpenAI GPT models (configurable)
- Message history pattern (SystemMessage → HumanMessage → AIMessage → ToolMessage)
- Answer synthesis from tool results

---

### Text-to-SQL Agent

**File:** `backend/app/agents/text_to_sql_agent.py`

Converts natural language queries to SQL and executes safely against SQLite databases.

**Tools (2):**
- `execute_sql_query`: Custom executor via SQLiteService with permission checks
- `sql_db_query_checker`: LangChain validator for syntax checking (optional, user-toggleable)

**Key Features:**
- **Multi-Step SQL Chains**: Can execute SELECT → UPDATE operations in sequence
- **Error Correction**: Message history enables retry on SQL errors
- **Permission System**: Checks allowed operations (SELECT/INSERT/UPDATE/DELETE) before execution
- **Query Limit**: Enforces max SQL queries per request (default: 3)
- **Deterministic**: Temperature 0.0 for consistent SQL generation

**Dynamic Prompt:**
- Pre-generated per database upload (~2K tokens)
- Includes schema, relationships, constraints, and query examples
- Cached in PostgreSQL for token efficiency
- User can regenerate or edit via UI

**Performance:**
- Simple queries: 2-3 seconds
- Multi-step queries: 7-8 seconds

**Example Flow:**
```
User: "Find highest rated movie and increase its rating by 1"
  ↓
Step 1: SELECT movie_id, imdb_rating FROM movies ORDER BY imdb_rating DESC LIMIT 1
Result: movie_id=101, imdb_rating=7.4
  ↓
Step 2: UPDATE movies SET imdb_rating = 8.4 WHERE movie_id = 101
Result: 1 row affected
  ↓
Answer: "Successfully increased rating from 7.4 to 8.4"
```

---

### RAG Agent

**File:** `backend/app/agents/rag_agent.py`

Semantic search over document chunks with multiple retrieval strategies.

**Tools (2):**
- `retrieve_records`: Multi-mode retrieval with metadata filtering
- `get_record`: Direct lookup by metadata filter

**Retrieval Modes (4):**
- **semantic**: Pgvector cosine similarity (best for conceptual queries)
- **keyword**: PostgreSQL full-text search with ts_rank (best for exact terms)
- **hybrid**: Reciprocal Rank Fusion combining both (best for complex queries)
- **neighbors**: Find similar records to a seed document (best for "find similar")

**Key Features:**
- **Multi-Turn Retry**: Automatically switches modes on empty results (max 3 iterations)
- **Metadata Filtering**: JSON-based filters with typed operators (int, str, list, bool)
- **Dataset-Aware**: Prompts generated per document upload, understanding domain-specific fields
- **Temperature 0.3**: Natural language answers

**Dynamic Prompt:**
- LLM-generated per document upload (~1.5-3K tokens)
- Analyzes metadata schema, sample records, and statistics
- Includes dataset-specific examples and filter templates
- User can regenerate or edit via UI

**Metadata Filter Example:**
```json
{
  "and": [
    {"field": "genres", "type": "list", "op": "contains", "value": "Crime"},
    {"field": "imdb_rating", "type": "int", "op": "greater_than", "value": 7}
  ]
}
```

**Example Flow:**
```
User: "Find films mentioning FBI"
  ↓
Step 1: retrieve_records(mode="keyword", query="FBI")
Result: 0 results
  ↓
Step 2: retrieve_records(mode="semantic", query="FBI federal investigation")
Result: 3 chunks
  ↓
Answer: "Found 3 films mentioning FBI themes..."
```

---

### Research Agent

**File:** `backend/app/agents/research_agent.py`

Web research using Google Custom Search API with citation tracking.

**Tools (1):**
- `web_search`: Performs web searches with automatic reference ID assignment

**Key Features:**
- **Multi-Turn Iteration**: Up to 10 searches per query for complex research
- **Citation Extraction**: Two-phase synthesis (answer + extract citations)
- **Reference Tracking**: Assigns ref_1, ref_2, etc. to all search results
- **Structured Output**: Uses Pydantic models for citation extraction
- **Temperature 0.3**: Balanced creativity for natural answers

**Citation System:**
1. Agent provides answer with [ref_N] citations
2. LLM extracts which references were actually cited
3. Response includes only cited references (fallback: deduplicated top 10)

**Configuration:**
- 5 results per search
- Max 3 searches per query (configurable)

**Example Flow:**
```
User: "Who directed Inception and what awards did it win?"
  ↓
Search 1: "Inception director"
Results: [ref_1: "Christopher Nolan", ref_2: "IMDb page"]
  ↓
Search 2: "Inception Academy Awards Oscars"
Results: [ref_3: "Won 4 Oscars", ref_4: "Nominations"]
  ↓
Answer: "Christopher Nolan directed Inception [ref_1]. The film won 4 Academy Awards [ref_3]..."
```

---

### Orchestrator

**File:** `backend/app/agents/orchestrator_agent.py`

LangGraph-based multi-agent coordinator using supervisor pattern.

**Architecture:**
- **Supervisor Node**: Selects which agent(s) to invoke
- **Agent Nodes**: Text-to-SQL, RAG, Research
- **State Graph**: Manages message flow and aggregation

**Key Features:**
- **Conversation Memory**: Persists history across requests in PostgreSQL
- **Parallel Execution**: Supports calling multiple agents simultaneously
- **Message Routing**: Routes responses between agents and user
- **Execution Metadata**: Tracks agent invocations, timings, and results

**Integration:**
- Coordinates all three specialized agents
- Manages user preferences (active RAG config, query checker settings)
- Handles conversation CRUD operations

---

## API Endpoints

### System
- `GET /` - Root endpoint
- `GET /health` - Health check

### Authentication (`/api/v1/auth`)
- `POST /register` - Register user after Firebase signup
- `GET /me` - Get current authenticated user

### Documents (`/api/v1/documents`)
- `POST /upload` - Upload PDF to Firebase Storage
- `GET /` - List user documents (own + public)
- `GET /{document_id}` - Get document with signed download URL
- `PATCH /{document_id}/public` - Toggle document visibility
- `DELETE /{document_id}` - Delete document

### Parsing Templates (`/api/v1/document-parsing`)
- `POST /generate` - LLM-generated template from document sample
- `POST /test-parse` - Test parse document with template
- `POST /` - Create template
- `GET /` - List templates
- `GET /{template_id}` - Get template
- `PUT /{template_id}` - Update template
- `DELETE /{template_id}` - Delete template

### Document Chunking (`/api/v1/document-chunking`)
- `POST /` - Create chunking process
- `GET /` - List chunking processes
- `GET /check-exists/{document_id}` - Check if chunking exists
- `GET /{id}` - Get chunking process
- `PUT /{id}` - Update chunking process
- `DELETE /{id}` - Delete chunking process

### RAG Prompts (`/api/v1/document-chunking`)
- `POST /generate-rag-prompt` - Generate RAG agent prompt
- `GET /rag-prompt` - Get current active RAG prompt
- `GET /available-rag-configs` - List all RAG configurations
- `GET /rag-prompt/{id}` - Get specific prompt
- `PATCH /rag-prompt` - Update prompt
- `POST /activate-rag-config` - Set active RAG data source

### SQLite (`/api/v1/sqlite`)
- `POST /upload` - Upload SQLite database (triggers background prompt generation)
- `GET /info` - Get database information
- `DELETE /` - Delete database
- `GET /schema` - Get database schema
- `POST /query` - Execute SQL query with permission checks
- `GET /tables/{table_name}/preview` - Get sample rows
- `PATCH /permissions` - Update allowed SQL operations
- `POST /generate-prompt` - Generate Text-to-SQL prompt
- `GET /agent-prompt` - Get current Text-to-SQL prompt
- `PATCH /agent-prompt` - Update prompt

### AI Agents (`/api/v1/agents`)
- `POST /text-to-sql` - Natural language to SQL
- `POST /rag` - RAG query over documents
- `POST /research` - Web research query
- `GET /settings` - Get user agent settings
- `PATCH /settings/query-checker` - Toggle query checker
- `GET /health` - Get agent health status

### Orchestrator (`/api/v1/orchestrator`)
- `POST /query` - Execute multi-agent query
- `POST /conversations` - Create conversation
- `GET /conversations` - List conversations
- `GET /conversations/{id}` - Get conversation
- `GET /conversations/{id}/messages` - Get messages
- `POST /conversations/{id}/messages` - Add message
- `DELETE /conversations/{id}` - Delete conversation

### Analytics (`/api/v1/analytics`)
- `GET /dashboard-metrics` - Get dashboard KPIs
- `GET /recent-activity` - Get recent activity feed

---

## Database Schema

**Users** (`users`):
- `id`, `email`, `display_name`, `created_at`, `updated_at`

**Documents** (`documents`):
- User-uploaded PDFs stored in Firebase Storage
- Tracks `file_name`, `storage_path`, `file_size`, `is_public`, `processing_status`

**Parsing Templates** (`parsing_templates`):
- LLM-generated or custom document parsing configurations
- Stores `template_json`, `parsed_record_preview`, `metadata_keywords`

**Document Chunking** (`document_chunking`):
- Chunking configurations linking documents to templates
- Tracks `name`, `description`, `agent_prompt`, `is_active`, `is_public`

**Document Chunks** (`document_chunks`):
- Parsed and embedded document chunks
- Contains `raw_object`, `llm_text`, `embedding_text`, `embedding` (pgvector 1536-dim)
- Stores `chunk_metadata` for filtering

**SQLite Databases** (`sqlite_databases`):
- User-uploaded SQLite files
- Tracks `database_name`, `storage_path`, `allowed_operations`, `sql_agent_prompt`

**Conversations** (`conversations`):
- Orchestrator conversation threads
- Links to user and contains messages

**Conversation Messages** (`conversation_messages`):
- Individual messages in conversations
- Stores `role`, `content`, `agent_metadata`

**User Preferences** (`user_preferences`):
- User settings (active RAG config, query checker enabled, etc.)

---

## Key Features

### Dynamic Prompt Generation

Both Text-to-SQL and RAG agents use LLM-generated prompts tailored to each dataset:

**Process:**
1. User uploads database or document
2. System extracts metadata (schema, sample data, statistics)
3. LLM analyzes structure and generates optimized prompt (~2-3K tokens)
4. Prompt stored in PostgreSQL for reuse
5. User can regenerate or manually edit via UI

**Benefits:**
- Dataset-specific guidance (field names, value ranges, relationships)
- Token-efficient (generated once, cached)
- Adaptable to any data structure

### Document Processing Pipeline

**Flow:**
```
PDF Upload → Template Generation → Parsing → Chunking → Embedding → Search
```

**Steps:**
1. **Upload**: PDF stored in Firebase Storage
2. **Template Generation**: LLM analyzes sample and creates parsing template
3. **Parsing**: Extract structured records using template
4. **Chunking**: Split into searchable chunks with metadata
5. **Embedding**: Generate 1536-dim OpenAI embeddings
6. **Storage**: Store in PostgreSQL with pgvector index

**Capabilities:**
- Supports any document structure (movies, products, papers, etc.)
- Metadata-based filtering (genres, ratings, dates, etc.)
- 4 retrieval modes (semantic, keyword, hybrid, neighbors)

### Multi-Agent Orchestration

LangGraph-based state machine coordinates multiple agents:

**Architecture:**
```
User Query → Supervisor → [Text-to-SQL | RAG | Research] → Aggregation → Response
```

**Features:**
- **Automatic Agent Selection**: Supervisor analyzes query and routes to appropriate agent(s)
- **Parallel Execution**: Can invoke multiple agents simultaneously
- **Context Sharing**: Agents can access previous conversation messages
- **Retry Logic**: Supervisor can retry with different agents on failure

**Example:**
```
Query: "Find the director of the highest-rated movie and research their awards"
  ↓
Supervisor → Text-to-SQL agent (find movie)
  ↓
Supervisor → Research agent (find director awards)
  ↓
Aggregated response with both results
```

### Permission System

**Document Access:**
- Users see own documents + public documents
- Document owners can toggle public/private status
- Public documents enable shared RAG configurations

**SQL Operations:**
- Per-database allowed operations (SELECT, INSERT, UPDATE, DELETE)
- Text-to-SQL agent checks permissions before execution
- Prevents unauthorized data modification

**Agent Features:**
- Query checker toggle (enable/disable SQL validation)
- Active RAG config selection (which document to query)
- Settings stored in user_preferences table

---

## Project Structure

```
backend/
├── alembic/                 # Database migrations
│   └── versions/
├── app/
│   ├── agents/              # AI agent implementations
│   │   ├── text_to_sql_agent.py
│   │   ├── rag_agent.py
│   │   ├── research_agent.py
│   │   └── orchestrator_agent.py
│   ├── api/
│   │   ├── v1/              # API version 1 endpoints
│   │   │   ├── auth.py
│   │   │   ├── documents.py
│   │   │   ├── document_parsing.py
│   │   │   ├── document_chunking.py
│   │   │   ├── sqlite.py
│   │   │   ├── agents.py
│   │   │   ├── orchestrator.py
│   │   │   └── analytics.py
│   │   └── deps.py          # Dependency injection
│   ├── core/
│   │   ├── config.py        # Settings & environment
│   │   ├── database.py      # Database connection
│   │   └── security.py      # Firebase authentication
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── document.py
│   │   ├── sqlite_database.py
│   │   ├── parsing_template.py
│   │   ├── document_chunking.py
│   │   ├── document_chunk.py
│   │   ├── conversation.py
│   │   └── user_preference.py
│   ├── repositories/        # Database access layer
│   │   ├── user_repository.py
│   │   ├── document_repository.py
│   │   ├── sqlite_database_repository.py
│   │   ├── template_repository.py
│   │   ├── document_chunking_repository.py
│   │   ├── document_chunk_repository.py
│   │   └── conversation_repository.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── user.py
│   │   ├── document.py
│   │   ├── template.py
│   │   ├── document_chunking.py
│   │   ├── sqlite.py
│   │   ├── text_to_sql.py
│   │   ├── rag.py
│   │   ├── research.py
│   │   └── orchestrator.py
│   ├── services/            # Business logic layer
│   │   ├── llm_service.py
│   │   ├── sqlite_service.py
│   │   ├── document_service.py
│   │   ├── template_service.py
│   │   ├── document_chunking_service.py
│   │   ├── rag_service.py
│   │   ├── conversation_service.py
│   │   ├── user_preferences_service.py
│   │   ├── analytics_service.py
│   │   ├── google_search_service.py
│   │   ├── prompt_generator_service.py
│   │   ├── rag_prompt_generator_service.py
│   │   ├── template_parser_service.py
│   │   ├── chunking_processor_service.py
│   │   └── firebase_storage_service.py
│   ├── prompts/             # Centralized prompt management
│   │   └── prompt_manager.py
│   └── main.py              # FastAPI application
├── docker-compose.yml       # PostgreSQL + pgvector
└── requirements.txt         # Python dependencies
```

---

## Development

### Database Migrations

**Create New Migration:**
```bash
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

**Rollback Migration:**
```bash
alembic downgrade -1
```

**Check Status:**
```bash
alembic current
alembic history
```

### Testing

**Swagger Documentation:**
- Production: https://appliedai-be.ismetseyhan.com/docs
- Local: http://localhost:8000/docs
- Test all endpoints with authentication

**Agent Health:**
```bash
# Production
curl https://appliedai-be.ismetseyhan.com/api/v1/agents/health

# Local
curl http://localhost:8000/api/v1/agents/health
```

### Stop Database
```bash
docker-compose down
```

### Reset Database
```bash
docker-compose down -v
docker-compose up -d
alembic upgrade head
```

### Background Tasks

Some endpoints trigger background processing:
- SQLite upload → Prompt generation
- Document upload → Parsing and embedding

Monitor logs for background task status.
