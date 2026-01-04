"""Admin notification service for critical errors and events.

This module provides functions to notify admins about important events
like errors, moderation blocks, and other critical situations.
"""

import logging
from typing import Optional

from bot.config import config

logger = logging.getLogger(__name__)


async def notify_admins(
    message: str,
    title: str = "🚨 Уведомление",
    parse_mode: str = "HTML",
) -> None:
    """
    Send notification to all admins.
    
    Args:
        message: Message text to send
        title: Title/header for the message
        parse_mode: Telegram parse mode (HTML or Markdown)
    """
    if not config.admin_ids:
        logger.warning("No admin IDs configured, skipping notification")
        return
    
    try:
        from aiogram import Bot
        
        bot = Bot(token=config.bot_token)
        
        full_message = f"<b>{title}</b>\n\n{message}"
        
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=full_message,
                    parse_mode=parse_mode,
                )
                logger.info(f"Admin {admin_id} notified: {title}")
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        await bot.session.close()
    
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")


async def notify_error(
    error: Exception,
    context: str = "",
    user_id: Optional[int] = None,
    username: Optional[str] = None,
) -> None:
    """
    Notify admins about an error.
    
    Args:
        error: The exception that occurred
        context: Additional context about where the error happened
        user_id: Telegram user ID if applicable
        username: Username if applicable
    """
    error_text = str(error)[:500]
    
    message_parts = []
    
    if context:
        message_parts.append(f"<b>Контекст:</b> {context}")
    
    if user_id:
        message_parts.append(f"<b>User ID:</b> <code>{user_id}</code>")
    
    if username:
        message_parts.append(f"<b>Username:</b> @{username}")
    
    message_parts.append(f"\n<b>Ошибка:</b>\n<code>{error_text}</code>")
    
    await notify_admins(
        message="\n".join(message_parts),
        title="🚨 Ошибка в боте",
    )


async def notify_moderation_block(
    user_id: int,
    username: Optional[str],
    prompt: str,
    error_msg: str,
) -> None:
    """
    Notify admins about content moderation block.
    
    Args:
        user_id: Telegram user ID
        username: Username
        prompt: The blocked prompt
        error_msg: Moderation error message
    """
    prompt_preview = prompt[:300] + "..." if len(prompt) > 300 else prompt
    
    message = (
        f"<b>User ID:</b> <code>{user_id}</code>\n"
        f"<b>Username:</b> @{username or 'N/A'}\n\n"
        f"<b>Промпт:</b>\n<code>{prompt_preview}</code>\n\n"
        f"<b>Причина:</b> {error_msg}"
    )
    
    await notify_admins(
        message=message,
        title="⚠️ Блокировка модерацией",
    )


async def notify_generation_failure(
    task_id: int,
    user_id: int,
    telegram_id: int,
    username: Optional[str],
    task_type: str,
    model: str,
    tokens_spent: int,
    prompt: str,
    error_msg: str,
) -> None:
    """
    Notify admins about generation failure.
    
    Args:
        task_id: Task database ID
        user_id: User database ID
        telegram_id: User's Telegram ID
        username: Username
        task_type: Type of task (generate/edit)
        model: Model used
        tokens_spent: Tokens that were spent
        prompt: The prompt
        error_msg: Error message
    """
    prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
    error_preview = error_msg[:500] + "..." if len(error_msg) > 500 else error_msg
    
    message = (
        f"<b>Task ID:</b> {task_id}\n"
        f"<b>User ID:</b> {user_id}\n"
        f"<b>Telegram ID:</b> <code>{telegram_id}</code>\n"
        f"<b>Username:</b> @{username or 'N/A'}\n"
        f"<b>Тип:</b> {task_type}\n"
        f"<b>Модель:</b> {model}\n"
        f"<b>Токены:</b> {tokens_spent}\n\n"
        f"<b>Промпт:</b>\n<code>{prompt_preview}</code>\n\n"
        f"<b>Ошибка:</b>\n<code>{error_preview}</code>"
    )
    
    await notify_admins(
        message=message,
        title="🚨 Ошибка генерации",
    )
