"""Monitoring service for forwarding user content to admin channel."""

import logging
from typing import Optional, List

from aiogram import Bot
from aiogram.types import Message

from bot.config import config

logger = logging.getLogger(__name__)


async def forward_source_photos_to_monitoring(
    bot: Bot,
    messages: List[Message],
    user_telegram_id: int,
    username: Optional[str],
    first_name: Optional[str],
    prompt: str,
    task_type: str = "edit",
) -> None:
    """
    Forward source photos to monitoring channel with user info.
    
    Args:
        bot: Bot instance
        messages: List of photo messages to forward
        user_telegram_id: User's Telegram ID
        username: User's username
        first_name: User's first name
        prompt: User's prompt
        task_type: Type of task (edit/generate)
    """
    if not config.monitoring_channel_id:
        return
    
    try:
        # Forward all photos
        for msg in messages:
            await bot.forward_message(
                chat_id=config.monitoring_channel_id,
                from_chat_id=msg.chat.id,
                message_id=msg.message_id,
            )
        
        # Send info message
        user_display = f"@{username}" if username else first_name or f"ID:{user_telegram_id}"
        
        info_text = (
            f"📸 <b>Исходные фото ({task_type})</b>\n\n"
            f"<b>Пользователь:</b> {user_display}\n"
            f"<b>Telegram ID:</b> <code>{user_telegram_id}</code>\n"
            f"<b>Количество фото:</b> {len(messages)}\n\n"
            f"<b>Промпт:</b>\n<i>{prompt[:500]}{'...' if len(prompt) > 500 else ''}</i>"
        )
        
        await bot.send_message(
            chat_id=config.monitoring_channel_id,
            text=info_text,
            parse_mode="HTML",
        )
        
        logger.info(f"Forwarded {len(messages)} source photos to monitoring channel for user {user_telegram_id}")
        
    except Exception as e:
        logger.error(f"Failed to forward source photos to monitoring channel: {e}")


async def forward_result_to_monitoring(
    bot: Bot,
    result_message: Message,
    user_telegram_id: int,
    username: Optional[str],
    first_name: Optional[str],
    task_id: int,
    task_type: str,
    model: str,
    quality: str,
    size: str,
    tokens_spent: int,
    prompt: str,
    generation_time: Optional[float] = None,
) -> None:
    """
    Forward generation result to monitoring channel with details.
    
    Args:
        bot: Bot instance
        result_message: Message with generated image
        user_telegram_id: User's Telegram ID
        username: User's username
        first_name: User's first name
        task_id: Task ID
        task_type: Type of task (edit/generate)
        model: Model used
        quality: Quality setting
        size: Size setting
        tokens_spent: Tokens spent
        prompt: User's prompt
        generation_time: Generation time in seconds
    """
    if not config.monitoring_channel_id:
        return
    
    try:
        # Forward result message
        await bot.forward_message(
            chat_id=config.monitoring_channel_id,
            from_chat_id=result_message.chat.id,
            message_id=result_message.message_id,
        )
        
        # Send details message
        user_display = f"@{username}" if username else first_name or f"ID:{user_telegram_id}"
        type_emoji = "🎨" if task_type == "generate" else "🪄"
        
        details_text = (
            f"{type_emoji} <b>Результат генерации</b>\n\n"
            f"<b>Task ID:</b> {task_id}\n"
            f"<b>Пользователь:</b> {user_display}\n"
            f"<b>Telegram ID:</b> <code>{user_telegram_id}</code>\n\n"
            f"<b>Модель:</b> {model}\n"
            f"<b>Качество:</b> {quality}\n"
            f"<b>Размер:</b> {size}\n"
            f"<b>Токены:</b> {tokens_spent} 🪙\n"
        )
        
        if generation_time:
            details_text += f"<b>Время:</b> {generation_time:.1f}с\n"
        
        details_text += f"\n<b>Промпт:</b>\n<i>{prompt[:500]}{'...' if len(prompt) > 500 else ''}</i>"
        
        await bot.send_message(
            chat_id=config.monitoring_channel_id,
            text=details_text,
            parse_mode="HTML",
        )
        
        logger.info(f"Forwarded result to monitoring channel for task {task_id}")
        
    except Exception as e:
        logger.error(f"Failed to forward result to monitoring channel: {e}")
