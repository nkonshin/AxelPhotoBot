"""Generation task processing for RQ worker.

This module contains the main task function that processes
image generation/editing requests asynchronously.
"""

import asyncio
import logging
import traceback
from typing import Optional

from redis import Redis
from rq import Queue, Retry

from bot.config import config
from bot.db.database import get_session_maker
from bot.db.models import GenerationTask
from bot.db.repositories import TaskRepository
from bot.services.balance import BalanceService
from bot.services.image_provider import (
    OpenAIImageProvider,
    SeeDreamImageProvider,
    GenerationResult,
    ImageProvider,
)
from bot.services.image_tokens import estimate_api_tokens, IMAGE_QUALITY_LABELS, get_actual_resolution
from bot.services.admin_notify import notify_generation_failure, notify_moderation_block

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
    return asyncio.run(
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
    telegram_id = None
    
    async with session_maker() as session:
        task_repo = TaskRepository(session)
        balance_service = BalanceService(session)
        
        # Get task from database
        task = await task_repo.get_by_id(task_id)
        if task is None:
            logger.error(f"Task {task_id} not found")
            return False
        
        # Get user's telegram_id
        from sqlalchemy import select
        from bot.db.models import User
        
        result = await session.execute(
            select(User.telegram_id).where(User.id == task.user_id)
        )
        telegram_id = result.scalar_one_or_none()
        
        # Update status to processing
        await task_repo.update_status(task_id, status="processing")
        logger.info(f"Task {task_id} status updated to processing")
        
        try:
            # Initialize image provider based on model
            image_provider: ImageProvider
            if task.model and task.model.startswith("seedream"):
                # Use SeeDream provider
                image_provider = SeeDreamImageProvider(
                    api_key=config.ark_api_key,
                    model="seedream-4-5-251128",
                )
            else:
                # Use OpenAI provider
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
            
            # Animation will be automatically replaced by result message
            
            if result.success and (result.image_url or result.image_base64):
                # Calculate API tokens for admin tracking
                api_tokens = estimate_api_tokens(task.image_quality, task.image_size)
                
                # Send result to user via Telegram
                file_id = await _send_result_to_user(
                    task,
                    result.image_url or result.image_base64 or "",
                    is_base64=result.image_base64 is not None and result.image_url is None,
                )

                if not file_id:
                    raise GenerationError("Failed to send result to user")

                # Success - update task with result and API tokens
                await task_repo.update_status(
                    task_id,
                    status="done",
                    result_image_url=result.image_url,
                    result_file_id=file_id,
                    api_tokens_spent=api_tokens,
                )
                
                # Update user's total API tokens spent
                await _update_user_api_tokens(session, task.user_id, api_tokens)
                
                logger.info(f"Task {task_id} completed successfully (API tokens: {api_tokens})")
                
                return True
            else:
                # API returned error - check if it's moderation error
                error_msg = result.error or "Unknown error"
                logger.warning(f"Task {task_id} generation failed: {error_msg}")
                
                # Check for moderation/content policy errors - no retry needed
                if "moderation" in error_msg.lower() or "safety" in error_msg.lower() or "content policy" in error_msg.lower():
                    raise ModerationError(error_msg)
                
                raise GenerationError(error_msg)
        
        except ModerationError as e:
            # Animation will be automatically replaced by error message
            
            error_msg = str(e)
            logger.warning(f"Task {task_id} blocked by moderation: {error_msg}")
            
            # Mark as failed immediately (no retries for moderation)
            await task_repo.update_status(
                task_id,
                status="failed",
                error_message="Content moderation",
            )
            
            # Refund tokens
            await balance_service.refund_task(task_id)
            logger.info(f"Task {task_id} marked as failed (moderation), tokens refunded")
            
            # Send moderation notification to user
            await _send_moderation_notification(task)
            
            # Notify admins
            from aiogram import Bot
            bot = Bot(token=config.bot_token)
            await _notify_admins_about_error(bot, task, error_msg)
            await bot.session.close()
            
            return False
        
        except Exception as e:
            # Animation will be automatically replaced by error message
            
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


class ModerationError(Exception):
    """Exception for content moderation failures (no retry needed)."""
    pass


async def _update_user_api_tokens(session, user_id: int, api_tokens: int) -> None:
    """
    Update user's total API tokens spent for admin tracking.
    
    Args:
        session: Database session
        user_id: User's database ID
        api_tokens: API tokens to add
    """
    try:
        from sqlalchemy import select
        from bot.db.models import User
        
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.api_tokens_spent += api_tokens
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to update user API tokens: {e}")


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
    import time
    start_time = time.time()
    
    try:
        from aiogram import Bot
        from aiogram.types import BufferedInputFile, URLInputFile
        from bot.keyboards.inline import result_feedback_keyboard
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
        
        db_time = time.time() - start_time
        logger.info(f"Task {task.id}: DB query took {db_time:.2f}s")
        
        # Stop progress animation by deleting it
        # We need to find the message with animation and delete it
        # Since we don't have message_id, we'll use a helper function
        from bot.utils.progress_animation import delete_progress_animation_for_user
        await delete_progress_animation_for_user(telegram_id, config.bot_token)
        
        # Send image to user
        task_type_emoji = "🎨" if task.task_type == "generate" else "🪄"
        task_type_text = "Картинка создана" if task.task_type == "generate" else "Фото отредактировано"
        quality_label = IMAGE_QUALITY_LABELS.get(task.image_quality, task.image_quality)
        
        # Get actual resolution based on model and quality
        actual_resolution = get_actual_resolution(task.model, task.image_quality, task.image_size)
        
        # Telegram caption limit is 1024 characters
        # Build static parts first to calculate remaining space for prompt
        static_text = (
            f"{task_type_emoji} <b>{task_type_text}!</b>\n\n"
            f"<blockquote expandable>PROMPT_PLACEHOLDER</blockquote>\n\n"
            f"⚙️ Качество: {quality_label} \n"
            f"💰 Списано: {task.tokens_spent} 🪙\n\n"
            f"💡 <i>Ответьте на это сообщение с новым описанием, чтобы отредактировать картинку</i>\n\n"
            f"❓ <b>Не понравился результат?</b>\n"
            f"• Попробуйте нашу новую модель в главном меню!\n"
            f"• Измените фото или добавьте другие\n"
            f"• Измените промпт или попробуйте один из шаблонов\n\n"
            f"Сделано в @AxelPhotobot"
        )
        
        # Calculate max prompt length: 1000 chars (safe margin) - static text length + placeholder length
        telegram_limit = 1000  # Safe margin below 1024
        placeholder_length = len("PROMPT_PLACEHOLDER")
        static_length = len(static_text) - placeholder_length
        max_prompt_length = telegram_limit - static_length
        
        # Ensure we have at least 100 chars for prompt
        if max_prompt_length < 100:
            max_prompt_length = 100
        
        # Truncate prompt if needed
        prompt_text = task.prompt if len(task.prompt) <= max_prompt_length else task.prompt[:max_prompt_length] + "..."
        
        # Build final caption
        caption = static_text.replace("PROMPT_PLACEHOLDER", prompt_text)

        # Generate filename based on model
        if task.model and task.model.startswith("seedream"):
            filename = "SeeDream-4.5.png"
        else:
            filename = "GPT_Image.png"

        # Try to send with full caption, fallback to shorter if too long
        sent = None
        caption_to_use = caption
        
        for attempt in range(2):
            try:
                if is_base64:
                    # Decode base64 and send as document
                    decode_start = time.time()
                    logger.info(f"Task {task.id}: Decoding base64 image, size: {len(image_data)} chars")
                    image_bytes = base64.b64decode(image_data)
                    decode_time = time.time() - decode_start
                    logger.info(f"Task {task.id}: Decoded to {len(image_bytes)} bytes in {decode_time:.2f}s")
                    
                    buffer_start = time.time()
                    document = BufferedInputFile(image_bytes, filename=filename)
                    buffer_time = time.time() - buffer_start
                    logger.info(f"Task {task.id}: BufferedInputFile created in {buffer_time:.2f}s")
                    
                    send_start = time.time()
                    logger.info(f"Task {task.id}: Sending document to user {telegram_id}")
                    sent = await bot.send_document(
                        chat_id=telegram_id,
                        document=document,
                        caption=caption_to_use,
                        parse_mode="HTML",
                        reply_markup=result_feedback_keyboard(task.id),
                    )
                    send_time = time.time() - send_start
                    logger.info(f"Task {task.id}: Document sent in {send_time:.2f}s")
                else:
                    # Send URL as document (Telegram will fetch it)
                    send_start = time.time()
                    logger.info(f"Task {task.id}: Sending URL document to user {telegram_id}")
                    
                    # Create URLInputFile with custom filename
                    url_file = URLInputFile(image_data, filename=filename)
                    
                    sent = await bot.send_document(
                        chat_id=telegram_id,
                        document=url_file,
                        caption=caption_to_use,
                        parse_mode="HTML",
                        reply_markup=result_feedback_keyboard(task.id),
                    )
                    send_time = time.time() - send_start
                    logger.info(f"Task {task.id}: URL document sent in {send_time:.2f}s")
                
                # Success - break the loop
                break
                
            except Exception as e:
                error_str = str(e)
                if "caption is too long" in error_str.lower() and attempt == 0:
                    # Caption still too long, try with minimal caption
                    logger.warning(f"Task {task.id}: Caption too long ({len(caption_to_use)} chars), retrying with minimal caption")
                    
                    # Minimal caption without tips
                    minimal_prompt = task.prompt[:200] + "..." if len(task.prompt) > 200 else task.prompt
                    caption_to_use = (
                        f"{task_type_emoji} <b>{task_type_text}!</b>\n\n"
                        f"<blockquote expandable>{minimal_prompt}</blockquote>\n\n"
                        f"⚙️ Качество: {quality_label}\n"
                        f"💰 Списано: {task.tokens_spent} 🪙\n\n"
                        f"Сделано в @AxelPhotobot"
                    )
                    continue
                else:
                    # Other error or second attempt failed
                    raise

        file_id = sent.document.file_id if sent and sent.document else None
        
        total_time = time.time() - start_time
        logger.info(f"Task {task.id}: Total _send_result_to_user time: {total_time:.2f}s")
        logger.info(f"Result sent to user {telegram_id} for task {task.id}")
        
        # Forward result to monitoring channel
        if config.monitoring_channel_id and sent:
            logger.info(f"Attempting to forward result to monitoring channel {config.monitoring_channel_id}")
            try:
                # Get user info
                session_maker_mon = get_session_maker()
                async with session_maker_mon() as session_mon:
                    from sqlalchemy import select
                    from bot.db.models import User
                    
                    result_user = await session_mon.execute(
                        select(User).where(User.id == task.user_id)
                    )
                    user = result_user.scalar_one_or_none()
                    
                    if user:
                        # Forward result message
                        await bot.forward_message(
                            chat_id=config.monitoring_channel_id,
                            from_chat_id=telegram_id,
                            message_id=sent.message_id,
                        )
                        
                        logger.info(f"Forwarded result message {sent.message_id} to monitoring channel")
                        
                        # Send details message
                        user_display = f"@{user.username}" if user.username else user.first_name or f"ID:{user.telegram_id}"
                        type_emoji = "🎨" if task.task_type == "generate" else "🪄"
                        
                        details_text = (
                            f"{type_emoji} <b>Результат генерации</b>\n\n"
                            f"<b>Task ID:</b> {task.id}\n"
                            f"<b>Пользователь:</b> {user_display}\n"
                            f"<b>Telegram ID:</b> <code>{user.telegram_id}</code>\n\n"
                            f"<b>Модель:</b> {task.model}\n"
                            f"<b>Качество:</b> {task.image_quality}\n"
                            f"<b>Размер:</b> {task.image_size}\n"
                            f"<b>Токены:</b> {task.tokens_spent} 🪙\n"
                            f"<b>Время:</b> {total_time:.1f}с\n\n"
                            f"<b>Промпт:</b>\n<i>{task.prompt[:500]}{'...' if len(task.prompt) > 500 else ''}</i>"
                        )
                        
                        await bot.send_message(
                            chat_id=config.monitoring_channel_id,
                            text=details_text,
                            parse_mode="HTML",
                        )
                        
                        logger.info(f"Forwarded result to monitoring channel for task {task.id}")
                    else:
                        logger.warning(f"User {task.user_id} not found for monitoring")
                        
            except Exception as e:
                logger.error(f"Failed to forward result to monitoring channel: {e}", exc_info=True)
        
        await bot.session.close()

        return file_id
    
    except Exception as e:
        logger.error(f"Failed to send result to user: {e}")
        return None


async def _send_failure_notification(task: GenerationTask, error_msg: str) -> None:
    """
    Send failure notification to user via Telegram.
    Also notifies admins about the error.
    
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
        
        # Stop progress animation
        from bot.utils.progress_animation import delete_progress_animation_for_user
        await delete_progress_animation_for_user(telegram_id, config.bot_token)
        
        # Send failure notification to user
        message = (
            f"❌ К сожалению, генерация не удалась.\n\n"
            f"Токены ({task.tokens_spent}) возвращены на ваш баланс.\n\n"
            f"Попробуйте ещё раз или измените промпт."
        )
        
        await bot.send_message(chat_id=telegram_id, text=message)
        
        logger.info(f"Failure notification sent to user {telegram_id} for task {task.id}")
        
        # Notify admins about the error
        await _notify_admins_about_error(bot, task, error_msg)
        
        await bot.session.close()
    
    except Exception as e:
        logger.error(f"Failed to send failure notification: {e}")


async def _send_moderation_notification(task: GenerationTask) -> None:
    """
    Send moderation notification to user when content is blocked.
    
    Args:
        task: GenerationTask that was blocked
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
        
        # Stop progress animation
        from bot.utils.progress_animation import delete_progress_animation_for_user
        await delete_progress_animation_for_user(telegram_id, config.bot_token)
        
        # Send moderation notification to user
        message = (
            f"⚠️ <b>Запрос отклонён фильтрами ИИ</b>\n\n"
            f"К сожалению, ваш запрос не прошёл проверку безопасности OpenAI.\n\n"
            f"Система сочла некоторые образы или слова недопустимыми (sexual content).\n\n"
            f"Токены ({task.tokens_spent}) возвращены на ваш баланс.\n\n"
            f"💡 <i>Попробуйте изменить описание и избегать запрещённого контента.</i>\n\n"
            f"<i>Или попробуйте переключить модель в меню бота (например на SeeDream 4.5 - у нее более мягкие фильтры).</i>"
        )
        
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="HTML")
        
        logger.info(f"Moderation notification sent to user {telegram_id} for task {task.id}")
        
        await bot.session.close()
    
    except Exception as e:
        logger.error(f"Failed to send moderation notification: {e}")


async def _notify_admins_about_error(bot, task: GenerationTask, error_msg: str) -> None:
    """
    Send error notification to all admins.
    
    Args:
        bot: Telegram Bot instance
        task: GenerationTask that failed
        error_msg: Error message
    """
    if not config.admin_ids:
        logger.warning("No admin IDs configured, skipping admin notification")
        return
    
    try:
        # Get user info for context
        session_maker = get_session_maker()
        async with session_maker() as session:
            from sqlalchemy import select
            from bot.db.models import User
            
            result = await session.execute(
                select(User.telegram_id, User.username).where(User.id == task.user_id)
            )
            user_data = result.first()
            user_telegram_id = user_data[0] if user_data else "Unknown"
            username = user_data[1] if user_data else "Unknown"
        
        # Build admin notification
        prompt_preview = task.prompt[:200] + "..." if len(task.prompt) > 200 else task.prompt
        error_preview = error_msg[:500] + "..." if len(error_msg) > 500 else error_msg
        
        admin_message = (
            f"🚨 <b>Ошибка генерации!</b>\n\n"
            f"<b>Task ID:</b> {task.id}\n"
            f"<b>User ID:</b> {task.user_id}\n"
            f"<b>Telegram ID:</b> {user_telegram_id}\n"
            f"<b>Username:</b> @{username if username else 'N/A'}\n"
            f"<b>Тип:</b> {task.task_type}\n"
            f"<b>Модель:</b> {task.model}\n"
            f"<b>Токены:</b> {task.tokens_spent}\n\n"
            f"<b>Промпт:</b>\n<code>{prompt_preview}</code>\n\n"
            f"<b>Ошибка:</b>\n<code>{error_preview}</code>"
        )
        
        # Send to all admins
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode="HTML",
                )
                logger.info(f"Admin {admin_id} notified about task {task.id} failure")
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    except Exception as e:
        logger.error(f"Failed to notify admins: {e}")
