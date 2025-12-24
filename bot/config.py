"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration."""
    
    # Telegram Bot
    bot_token: str
    webhook_url: str
    
    # Database
    database_url: str
    
    # Redis
    redis_url: str
    
    # OpenAI
    openai_api_key: str
    
    # App settings
    initial_tokens: int


def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        bot_token=os.getenv("BOT_TOKEN", ""),
        webhook_url=os.getenv("WEBHOOK_URL", ""),
        database_url=os.getenv("DATABASE_URL", ""),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        initial_tokens=int(os.getenv("INITIAL_TOKENS", "10")),
    )


# Global config instance
config = load_config()
