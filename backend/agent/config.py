"""
Configuration settings for the Health Agent.
Loads environment variables and provides centralized config access.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Anthropic API
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    
    # MongoDB Atlas
    mongodb_uri: str = os.getenv("MONGODB_URI", "")
    mongodb_database: str = os.getenv("MONGODB_DATABASE", "health_data")
    
    # Health Data Collection
    health_data_collection: str = os.getenv("HEALTH_DATA_COLLECTION", "health_data")
    
    # Memory/Checkpointing
    checkpoint_collection: str = os.getenv("CHECKPOINT_COLLECTION", "checkpoints")
    conversations_collection: str = os.getenv("CONVERSATIONS_COLLECTION", "conversations")
    
    # Agent Settings
    max_clarification_turns: int = 3
    max_parallel_subagents: int = 5
    subagent_timeout_seconds: int = 60
    
    # Streaming
    streaming_enabled: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def get_mongo_client():
    """Get MongoDB client instance."""
    from pymongo import MongoClient
    return MongoClient(settings.mongodb_uri)


def get_async_mongo_client():
    """Get async MongoDB client instance."""
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(settings.mongodb_uri)


def get_llm(temperature: float = 0.7, streaming: bool = True):
    """Get configured Anthropic LLM instance."""
    from langchain_anthropic import ChatAnthropic
    
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=temperature,
        streaming=streaming,
    )
