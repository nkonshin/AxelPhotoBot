"""Generation task processing for RQ worker.

This module contains the main task function that processes
image generation/editing requests asynchronously.
"""

import asyncio
import logging
from typing import Optional

from redis import Redis
from rq import Queue, Retry

from bot.config import config
from bot.db.database import get_session_maker
from bot.db.models import GenerationTask
from bot.db.repositories import TaskRepository
from bot.services.balance import BalanceService
from bot.services.image_provider import OpenAIImageProvider, GenerationResult

logger = logging.getLogger(__name__)

# Maximum retry attempts (handled by RQ, but we track in DB too)
MAX_RETRIES = 3

# RQ Queue instance (lazy initialization)
_queue: Optional[Queue] = None


def get_queue() -> Queue:
    """Get or create the RQ queue instance."""
    global _queue
    if _queue is None:
        redis_conn = Redis.from_url(config.redis_url)
        _queue = Queue(connection=redis_conn)
    return _queue


def enqueue_generation_task(task_id: int) -> None:
    """
    Enqueue a generation task to RQ.
    
    Args:
        task_id: Database ID of the GenerationTask
    """
    queue = get_queue()
    
    # Enqueue with retry policy: 3 attempts with exponential backoff
    job = queue.enqueue(
        process_generation_task,
        task_id,
        retry=Retry(max=MAX_RETRIES, interval=[10, 30, 60]),
    )
    
    logger.info(f"Enqueued task {task_id} as job {job.id}")


def process_generation_task(task_id: int) -> bool:
    """
    Process a generation task.
    
    This is the main RQ task function that:
    1. Updates task status to "processing"
    2. Calls OpenAI API for generation/editing
    3. Updates task status to "done" or "failed"
    4. Sends result to user via Telegram
    5. Refunds tokens on failure
    
    Args:
        task_id: Database ID of the GenerationTask
    
    Returns:
        True if successful, False otherwise
    
    Raises:
        Exception: Re-raised for RQ retry mechanism
    """
    # Run async code in sync context (RQ workers are sync)
    return asyncio.get_event_loop().run_until_complete(
        _process_generation_task_async(task_id)
    )


async def _process_generation_task_async(task_id: int) -> bool:
    """
    Async implementation of generation task processing.
    
    Args:
        task_id: Database ID of the GenerationTask
    
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Processing generation task {task_id}")
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        task_repo = TaskRepository(session)
        balance_service = BalanceService(session)
        
        # Get task from database
        task = await task_repo.get_by_id(task_id)
        if task is None:
            logger.error(f"Task {task_id} not found")
            return False
        
        # Update status to processing
        await task_repo.update_status(task_id, status="processing")
        logger.info(f"Task {task_id} status updated to processing")
        
        try:
            # Initialize image provider with task model
            image_provider = OpenAIImageProvider(
                api_key=config.openai_api_key,
                model=task.model or "gpt-image-1",
            )
            
            # Generate or edit based on task type
            result: GenerationResult
            if task.task_type == "generate":
                result = await image_provider.generate(
                    task.prompt,
                    model=task.model,
                    quality=task.image_quality,
                    size=task.image_size,
                )
            elif task.task_type == "edit":
                if task.source_image_url is None:
                    raise ValueError("Edit task requires source_image_url")
                # Pass bot token for Telegram file download
                result = await image_provider.edit(
                    task.source_image_url,
                    task.prompt,
                    bot_token=config.bot_token,
                    model=task.model,
                    quality=task.image_quality,
                    size=task.image_size,
                )
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            if result.success and (result.image_url or result.image_base64):
                # Send result to user via Telegram
                file_id = await _send_result_to_user(
                    task,
                    result.image_url or result.image_base64 or "",
                    is_base64=result.image_base64 is not None and result.image_url is None,
                )

                if not file_id:
                    raise GenerationError("Failed to send result to user")

                # Success - update task with result
                await task_repo.update_status(
                    task_id,
                    status="done",
                    result_image_url=result.image_url,
                    result_file_id=file_id,
                )
                logger.info(f"Task {task_id} completed successfully")
                
                return True
            else:
                # API returned error - raise for retry
                error_msg = result.error or "Unknown error"
                logger.warning(f"Task {task_id} generation failed: {error_msg}")
                raise GenerationError(error_msg)
        
        except Exception as e:
            # Handle failure
            error_msg = str(e)
            logger.error(f"Task {task_id} failed with error: {error_msg}")
            
            # Refresh task to get current retry count
            task = await task_repo.get_by_id(task_id)
            if task is None:
                return False
            
            current_retry = task.retry_count + 1
            
            if current_retry >= MAX_RETRIES:
                # All retries exhausted - mark as failed and refund
                await task_repo.update_status(
                    task_id,
                    status="failed",
                    error_message=error_msg,
                    increment_retry=True,
                )
                
                # Refund tokens
                await balance_service.refund_task(task_id)
                logger.info(f"Task {task_id} marked as failed, tokens refunded")
                
                # Notify user about failure
                await _send_failure_notification(task, error_msg)
                
                return False
            else:
                # Increment retry count and re-raise for RQ retry
                await task_repo.update_status(
                    task_id,
                    status="pending",
                    error_message=error_msg,
                    increment_retry=True,
                )
                logger.info(
                    f"Task {task_id} retry {current_retry}/{MAX_RETRIES}, "
                    f"re-queuing..."
                )
                raise  # Re-raise for RQ retry mechanism


class GenerationError(Exception):
    """Custom exception for generation failures."""
    pass


async def _send_result_to_user(
    task: GenerationTask,
    image_data: str,
    is_base64: bool = False,
) -> Optional[str]:
    """
    Send generated image to user via Telegram.
    
    Args:
        task: GenerationTask with user info
        image_data: URL of the generated image or base64 string
        is_base64: Whether image_data is base64 encoded
    """
    try:
        from aiogram import Bot
        from aiogram.types import BufferedInputFile
        from bot.keyboards.inline import regenerate_keyboard
        import base64
        
        bot = Bot(token=config.bot_token)
        
        # Get user's telegram_id from task's user relationship
        session_maker = get_session_maker()
        async with session_maker() as session:
            from sqlalchemy import select
            from bot.db.models import User
            
            result = await session.execute(
                select(User.telegram_id).where(User.id == task.user_id)
            )
            telegram_id = result.scalar_one_or_none()
            
            if telegram_id is None:
                logger.error(f"User {task.user_id} not found for task {task.id}")
                return None
        
        # Send image to user
        task_type_emoji = "🎨" if task.task_type == "generate" else "✏️"
        task_type_text = "Картинка создана" if task.task_type == "generate" else "Фото отредактировано"
        prompt_preview = task.prompt[:300] + "..." if len(task.prompt) > 300 else task.prompt
        
        caption = (
            f"{task_type_emoji} <b>{task_type_text}!</b>\n\n"
            f"<blockquote>{prompt_preview}</blockquote>\n\n"
            f"⚙️ {task.image_quality} • {task.image_size}\n"
            f"💰 Списано: {task.tokens_spent} 🪙\n\n"
            f"💡 <i>Ответьте на это сообщение с новым описанием, чтобы отредактировать картинку</i>"
        )

        # Filename: GPT_Image_{task_id}.png
        filename = f"GPT_Image_{task.id}.png"

        if is_base64:
            # Decode base64 and send as document
            image_bytes = base64.b64decode(image_data)
            document = BufferedInputFile(image_bytes, filename=filename)
            sent = await bot.send_document(
                chat_id=telegram_id,
                document=document,
                caption=caption,
                reply_markup=regenerate_keyboard(task.id),
            )
        else:
            # Send URL as document (Telegram will fetch it)
            sent = await bot.send_document(
                chat_id=telegram_id,
                document=image_data,
                caption=caption,
                reply_markup=regenerate_keyboard(task.id),
            )

        file_id = sent.document.file_id if sent and sent.document else None
        
        logger.info(f"Result sent to user {telegram_id} for task {task.id}")
        
        await bot.session.close()

        return file_id
    
    except Exception as e:
        logger.error(f"Failed to send result to user: {e}")
        return None


async def _send_failure_notification(task: GenerationTask, error_msg: str) -> None:
    """
    Send failure notification to user via Telegram.
    
    Args:
        task: GenerationTask with user info
        error_msg: Error message to include
    """
    try:
        from aiogram import Bot
        
        bot = Bot(token=config.bot_token)
        
        # Get user's telegram_id
        session_maker = get_session_maker()
        async with session_maker() as session:
            from sqlalchemy import select
            from bot.db.models import User
            
            result = await session.execute(
                select(User.telegram_id).where(User.id == task.user_id)
            )
            telegram_id = result.scalar_one_or_none()
            
            if telegram_id is None:
                logger.error(f"User {task.user_id} not found for task {task.id}")
                return
        
        # Send failure notification
        message = (
            f"❌ К сожалению, генерация не удалась.\n\n"
            f"Токены ({task.tokens_spent}) возвращены на ваш баланс.\n\n"
            f"Попробуйте ещё раз или измените промпт."
        )
        
        await bot.send_message(chat_id=telegram_id, text=message)
        
        logger.info(f"Failure notification sent to user {telegram_id} for task {task.id}")
        
        await bot.session.close()
    
    except Exception as e:
        logger.error(f"Failed to send failure notification: {e}")
