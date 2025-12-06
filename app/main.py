from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.is_development,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoints (no prefix)
@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Multi-Agent Movie System API",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": "backend-api"
    }


api_router = APIRouter()
app.include_router(api_router, prefix=settings.API_BASE_PREFIX)
