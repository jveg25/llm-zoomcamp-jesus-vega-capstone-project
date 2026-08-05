from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from .env / environment variables."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str                     # no default: fail fast if missing
    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    llm_provider: str = "openai"
    llm_model: str = "gpt-5.4-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536               # must match vector(1536) in the schema
    price_prompt_per_1m: float = 0.15       # USD per 1M input tokens — verify at openai.com/api/pricing
    price_completion_per_1m: float = 0.60   # USD per 1M output tokens
    supabase_jwt_secret: str = ""
    monthly_question_limit: int = 500       # per non-admin account; 0 disables the cap

settings = Settings()