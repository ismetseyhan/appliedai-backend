# Multi-Agent Movie System - Backend API

FastAPI backend with Firebase authentication and PostgreSQL database.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Setup Environment
```bash
cp .env.example .env
# Add your Firebase service account JSON
```

### 3. Start PostgreSQL (Docker)
```bash
docker-compose up -d
```

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
- Swagger Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Database Migrations

### Create New Migration
```bash
# After changing models, auto-generate migration
alembic revision --autogenerate -m "Description of change"

# Apply migration
alembic upgrade head
```

### Rollback Migration
```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade <revision_id>
```

### Check Migration Status
```bash
# Show current version
alembic current

# Show migration history
alembic history
```

## Project Structure
```
backend/
├── alembic/              # Database migrations
│   └── versions/         # Migration files
├── app/
│   ├── api/
│   │   ├── v1/           # API version 1
│   │   │   └── auth.py   # Authentication endpoints
│   │   └── deps.py       # Shared dependencies
│   ├── core/
│   │   ├── config.py     # Settings & environment
│   │   ├── database.py   # Database connection
│   │   └── security.py   # Firebase authentication
│   ├── models/
│   │   └── user.py       # SQLAlchemy models
│   ├── schemas/
│   │   └── user.py       # Pydantic schemas
│   └── main.py           # FastAPI application
├── docker-compose.yml    # PostgreSQL + pgvector
└── requirements.txt      # Python dependencies
```

## API Endpoints

### System
- `GET /` - Root
- `GET /health` - Health check

### Authentication (v1)
- `POST /api/v1/auth/register` - Register user after Firebase signup
- `GET /api/v1/auth/me` - Get current user info

## Development

### Stop Database
```bash
docker-compose down
```

### Reset Database
```bash
# Drop all tables and rerun migrations
docker-compose down -v
docker-compose up -d
alembic upgrade head
```
