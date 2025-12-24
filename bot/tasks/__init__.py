"""RQ tasks module for async task processing.

This module provides Redis Queue (RQ) integration for handling
image generation tasks asynchronously.
"""

import logging
from typing import Optional

from redis import Redis
from rq import Queue, Retry

from bot.config import config

logger = logging.getLogger(__name__)

# Redis connection instance
_redis_conn: Optional[Redis] = None

# Default queue instance
_default_queue: Optional[Queue] = None

# Retry policy: 3 attempts with exponential backoff (10s, 30s, 60s)
DEFAULT_RETRY = Retry(max=3, interval=[10, 30, 60])


def get_redis_connection() -> Redis:
    """
    Get or create Redis connection.
    
    Returns:
        Redis connection instance
    """
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = Redis.from_url(config.redis_url)
        logger.info(f"Connected to Redis at {config.redis_url}")
    return _redis_conn


def get_queue(name: str = "default") -> Queue:
    """
    Get or create an RQ queue.
    
    Args:
        name: Queue name (default: "default")
    
    Returns:
        RQ Queue instance
    """
    global _default_queue
    if name == "default" and _default_queue is not None:
        return _default_queue
    
    conn = get_redis_connection()
    queue = Queue(name=name, connection=conn)
    
    if name == "default":
        _default_queue = queue
    
    return queue


def enqueue_generation_task(task_id: int) -> str:
    """
    Enqueue a generation task for processing.
    
    Args:
        task_id: Database ID of the GenerationTask
    
    Returns:
        RQ job ID
    """
    from bot.tasks.generation import process_generation_task
    
    queue = get_queue()
    job = queue.enqueue(
        process_generation_task,
        task_id,
        retry=DEFAULT_RETRY,
        job_timeout="5m",  # 5 minute timeout for image generation
    )
    
    logger.info(f"Enqueued generation task {task_id} with job ID {job.id}")
    return job.id


def close_redis_connection() -> None:
    """Close Redis connection."""
    global _redis_conn, _default_queue
    if _redis_conn is not None:
        _redis_conn.close()
        _redis_conn = None
        _default_queue = None
        logger.info("Redis connection closed")
