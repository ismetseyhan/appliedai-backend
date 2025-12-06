# Multi-Agent Movie System - FAST API Backend

Multi-agent system for movie intelligence.

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env if needed (defaults work for now)
   ```

3. **Run server**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. **Test**
   - API Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

## Project Structure
```
backend/
├── app/
│   ├── main.py           # FastAPI app
│   └── core/
│       └── config.py     # Settings
├── requirements.txt      # Dependencies
└── README.md
```
