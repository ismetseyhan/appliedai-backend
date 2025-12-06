from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "Multi-Agent Movie System"
    API_BASE_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS_STR: str = "http://localhost:3000,http://localhost:3001"

    class Config:
        env_file = ".env"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",")]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"


settings = Settings()
