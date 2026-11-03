from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Thai Naturals AI Shopping Assistant"
    store_name: str = "Thai Naturals"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    llm_provider: str = "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"

    storage_backend: str = "memory"
    database_url: str = ""
    catalog_provider: str = "memory"
    catalog_cache_seconds: int = 60
    shopify_store_domain: str = ""
    shopify_storefront_access_token: str = ""
    shopify_api_version: str = "2026-10"
    catalog_api_type: str = "rest"
    catalog_api_url: str = ""
    catalog_api_token: str = ""
    catalog_api_query: str = ""
    catalog_database_url: str = ""
    catalog_sql_query: str = ""

    chat_history_limit: int = 20
    payment_provider: str = "dummy"
    enable_demo_payment_endpoint: bool = True

    currency: str = Field(default="INR", min_length=3, max_length=3)
    default_shipping_fee: float = Field(default=50, ge=0)
    default_free_shipping_threshold: float = Field(default=1499, ge=0)
    store_policies_json: str = ""

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
