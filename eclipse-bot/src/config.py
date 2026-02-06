"""Configuration management for Eclipse Bot."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Slack Configuration
    slack_app_token: str
    slack_bot_token: str

    # Perforce Configuration
    p4user: str = "ecl_server"
    p4client: str = "Server-Linux-Agent"
    p4port: str = "p4d-ecl.npixel.work:1666"
    p4passwd: str = ""

    # AI Configuration
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    
    # Persistence Configuration
    persistence_db_path: str = "/data4/db/eclipse_bot.db"
    persistence_fallback_path: str = "/tmp/db/eclipse_bot.db"
    
    # Models
    default_model: str = "moonshotai/kimi-k2.5" 
    
    # OpenSearch Configuration
    opensearch_url: str = ""
    opensearch_username: str = ""
    opensearch_password: str = ""
    opensearch_index_pattern: str = "fluent-bit-*"
# Default OpenRouter model
    main_agent_model: str = "" # Fallback to default_model in code
    subagent_model: str = ""   # Fallback to default_model in code
    
    # UI/UX Settings
    streaming_throttle_interval: float = 0.8

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get singleton settings instance."""
    return Settings()
