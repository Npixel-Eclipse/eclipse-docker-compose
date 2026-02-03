"""Configuration management using Pydantic Settings and YAML."""

import os
import re
import yaml
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, List, Optional
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Slack Configuration
    slack_app_token: str
    slack_bot_token: str

    # OpenRouter Configuration
    openrouter_api_key: str
    default_model: str = "google/gemini-3-flash-preview"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"


    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ConfigLoader:
    """Loads configuration from YAML files with environment variable substitution."""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Load YAML config and substitute env vars."""
        path = Path(self.config_path)
        if not path.exists():
            logger.warning(f"Config file not found at {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Substitute ${VAR} with environment variables
        content = self._substitute_env_vars(content)
        
        try:
            self._config = yaml.safe_load(content) or {}
            logger.info(f"Loaded config from {path}")
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")

    def _substitute_env_vars(self, content: str) -> str:
        """Replace ${VAR} with value from os.environ."""
        pattern = re.compile(r'\$\{([^}^{]+)\}')
        
        def replace(match):
            env_var = match.group(1)
            return os.environ.get(env_var, match.group(0))  # Return original if not found
            
        return pattern.sub(replace, content)

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by key (dot notation supported)."""
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
                
            if value is None:
                return default
                
        return value

@lru_cache
def get_settings() -> Settings:
    """Get cached env settings instance."""
    return Settings()

@lru_cache
def get_config() -> ConfigLoader:
    """Get cached YAML config instance."""
    return ConfigLoader()
