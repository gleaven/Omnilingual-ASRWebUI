"""Application configuration."""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # App Info
    APP_NAME: str = "Omnilingual ASR Web"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8123

    # Database
    DATABASE_URL: str = "sqlite:///./omniasr.db"

    # Redis (for Celery)
    REDIS_URL: str = "redis://redis:6379/0"

    # Storage
    STORAGE_PATH: str = "/app/storage"
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS: List[str] = [
        "mp3", "wav", "m4a", "flac", "ogg", "webm", "mp4",
        "avi", "mkv", "mov", "aac", "wma", "aiff"
    ]

    # Processing
    DEFAULT_MODEL: str = "CTC_1B"  # Changed from LLM_7B for faster processing
    CHUNK_DURATION: int = 30
    ENABLE_DIARIZATION: bool = True
    MAX_AUDIO_DURATION: int = 36000  # 10 hours in seconds

    # ASR Models
    MODEL_CACHE_DIR: str = "/root/.cache/fairseq2/assets"
    DEVICE: str = "cuda"  # Will fall back to CPU if CUDA not available
    DTYPE: str = "float32"  # or "bfloat16"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8123"]

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
