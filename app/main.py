from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.core.config import settings
from app.core.security import initialize_firebase
from app.api.v1 import auth, documents, sqlite, llm, agents, parsing_templates, document_chunking

# Initialize Firebase
initialize_firebase()

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.is_development,
)


#  OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="Multi-Agent Movie Intelligence System API with Firebase Authentication",
        routes=app.routes,
    )
    # HTTPBearer description
    if "securitySchemes" in openapi_schema.get("components", {}):
        if "HTTPBearer" in openapi_schema["components"]["securitySchemes"]:
            openapi_schema["components"]["securitySchemes"]["HTTPBearer"]["description"] = "Enter your Firebase ID token (without 'Bearer' prefix)"
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

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

# Include auth router
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)
# documents router
api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"]
)
# sqlite router
api_router.include_router(
    sqlite.router,
    prefix="/sqlite",
    tags=["SQLite Databases"]
)
# llm router
api_router.include_router(
    llm.router,
    prefix="/llm",
    tags=["LLM / AI"]
)
# agents router
api_router.include_router(
    agents.router,
    prefix="/agents",
    tags=["AI Agents"]
)
# parsing templates router
api_router.include_router(
    parsing_templates.router,
    prefix="/document-parsing",
    tags=["Document Parsing Templates"]
)
# document_chunking router
api_router.include_router(
    document_chunking.router,
    prefix="/document-chunking",
    tags=["Document Chunking"]
)

# API v1 router
app.include_router(api_router, prefix=f"{settings.API_BASE_PREFIX}/v1")
