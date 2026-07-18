"""
Centralized app configuration, loaded from environment variables / .env.

Every field is optional except JWT_SECRET in production -- the app is
designed to boot with zero configuration for local demoing.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "omnimind"
    JWT_SECRET: str = "dev-only-insecure-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # LLM providers
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    OMNIMIND_FORCE_PROVIDER: str | None = None

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:3000"


settings = Settings()
