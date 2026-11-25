from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Operations Assistant"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str):
            return json.loads(v)
        return v

    # Database
    DATABASE_URL: str = "sqlite:///./ai_ops.db"

    # AI Provider Selection: "gemini" (default), "openai", or "demo"
    LLM_PROVIDER: str = "gemini"

    # Google Gemini Configuration
    GEMINI_API_KEY: str = ""
    # OpenAI Configuration (optional fallback provider)
    OPENAI_API_KEY: str = ""

    # Model Configuration
    LLM_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "text-embedding-004"
    # Vector Dimension (384 for demo & text-embedding-004 output_dimensionality, 768 for native text-embedding-004, 1536 for OpenAI)
    EMBEDDING_DIMENSION: int = 384

    @property
    def active_provider(self) -> str:
        """
        Determines the active provider based on LLM_PROVIDER and key availability.
        Returns 'gemini', 'openai', or 'demo'.
        """
        provider = (self.LLM_PROVIDER or "gemini").strip().lower()
        if provider == "gemini":
            if self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip():
                return "gemini"
            return "demo"
        elif provider == "openai":
            if self.OPENAI_API_KEY and self.OPENAI_API_KEY.strip():
                return "openai"
            return "demo"
        elif provider == "demo":
            return "demo"
        # Fallback check if provider string is unrecognized
        if self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip():
            return "gemini"
        elif self.OPENAI_API_KEY and self.OPENAI_API_KEY.strip():
            return "openai"
        return "demo"

    @property
    def is_demo_mode(self) -> bool:
        return self.active_provider == "demo"

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
