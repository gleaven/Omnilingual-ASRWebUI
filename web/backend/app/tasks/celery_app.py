"""Celery application configuration."""

from celery import Celery
from ..core.config import settings

# Create Celery app
celery_app = Celery(
    "omniasr_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks.transcription_tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=7200,  # 2 hours max per task (increased from 1 hour)
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (keep model in memory longer)
    broker_connection_retry_on_startup=True,  # Fix deprecation warning
)
