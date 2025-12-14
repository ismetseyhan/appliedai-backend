from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "Multi-Agent Movie System"
    API_BASE_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS_STR: str = "http://localhost:3000,http://localhost:3001"

    # Firebase service account JSON file path
    GOOGLE_APPLICATION_CREDENTIALS: str = "./firebase-service-account.json"

    # Firebase Storage
    FIREBASE_STORAGE_BUCKET: str

    # OpenAI Configuration
    OPENAI_API_KEY: str  # env
    OPENAI_MODEL_NAME: str = "gpt-4o"  # Default
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"  # 1536 dims
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # Google Custom Search Configuration
    GOOGLE_SEARCH_API_KEY: str = ""
    GOOGLE_SEARCH_ENGINE_ID: str = ""
    GOOGLE_SEARCH_MAX_RESULTS: int = 10

    # Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str  # Must be set in .env
    DB_NAME: str = "movieapp"

    class Config:
        env_file = ".env"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",")]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"


settings = Settings()
