"""Configuration module using pydantic-settings."""
import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Application configuration loaded from environment / .env."""

    openai_api_key: str = Field(..., description="OpenAI API key")
    google_maps_api_key: str = Field(..., description="Google Maps API key")
    target_region: str = Field(default="Cyberjaya", description="Target region for lead gen")
    target_country: str = Field(default="Malaysia", description="Target country")
    max_results_per_search: int = Field(default=20, ge=1, le=60, description="Max results per query")
    output_dir: str = Field(default="output", description="Directory for output artifacts")
    llm_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="LLM sampling temperature")
    n8n_webhook_url: Optional[str] = Field(default=None, description="Optional n8n webhook URL")
    resend_api_key: Optional[str] = Field(default=None, description="Optional Resend API key")

    @field_validator("output_dir")
    @classmethod
    def ensure_output_dir(cls, value: str) -> str:
        os.makedirs(value, exist_ok=True)
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return a singleton Config instance."""
    return Config()
