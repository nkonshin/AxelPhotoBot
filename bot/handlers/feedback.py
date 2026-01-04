"""Feedback handlers for generation results.

Handles user feedback (👍/👎) and retry functionality.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.db.database import get_session_maker
from bot.db.repositories import TaskRepository, UserRepository
from bot.keyboards.inline import (
    CallbackData,
    negative_feedback_keyboard,
)
from bot.services.image_tokens import calculate_total_cost
from bot.tasks.generation import enqueue_generation_task

logger = logging.getLogger(__name__)

router = Router(name="feedback")


@router.callback_query(F.data.startswith(CallbackData.FEEDBACK_POSITIVE_PREFIX))
async def handle_positive_feedback(callback: CallbackQuery) -> None:
    """Handle positive feedback (👍) - just acknowledge."""
    task_id = int(callback.data.replace(CallbackData.FEEDBACK_POSITIVE_PREFIX, ""))
    
    logger.info(f"Positive feedback for task {task_id} from user {callback.from_user.id}")
    
    await callback.answer("Спасибо за отзыв! 🙏", show_alert=False)


@router.callback_query(F.data.startswith(CallbackData.FEEDBACK_NEGATIVE_PREFIX))
async def handle_negative_feedback(callback: CallbackQuery) -> None:
    """Handle negative feedback (👎) - show retry options."""
    task_id = int(callback.data.replace(CallbackData.FEEDBACK_NEGATIVE_PREFIX, ""))
    
    logger.info(f"Negative feedback for task {task_id} from user {callback.from_user.id}")
    
    await callback.message.edit_reply_markup(
        reply_markup=negative_feedback_keyboard(task_id)
    )
    await callback.answer("Жаль, что не понравилось 😔", show_alert=False)


@router.callback_query(F.data.startswith(CallbackData.FEEDBACK_RETRY_PREFIX))
async def handle_retry(callback: CallbackQuery) -> None:
    """Handle retry request from negative feedback - regenerate with token cost."""
    task_id = int(callback.data.replace(CallbackData.FEEDBACK_RETRY_PREFIX, ""))
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        task_repo = TaskRepository(session)
        user_repo = UserRepository(session)
        
        # Get original task
        original_task = await task_repo.get_by_id(task_id)
        if not original_task:
            await callback.answer("Задача не найдена", show_alert=True)
            return
        
        # Get user
        user = await user_repo.get_by_id(original_task.user_id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Calculate token cost (same as original)
        token_cost = calculate_total_cost(original_task.image_quality)
        
        # Check balance
        if user.tokens < token_cost:
            await callback.answer(
                "Ой! Кажется, токены закончились 📸",
                show_alert=True
            )
            return
        
        # Deduct tokens
        await user_repo.update_tokens(user.id, -token_cost)
        
        # Create new task with same parameters
        new_task = await task_repo.create(
            user_id=user.id,
            task_type=original_task.task_type,
            prompt=original_task.prompt,
            source_image_url=original_task.source_image_url,
            model=original_task.model,
            image_quality=original_task.image_quality,
            image_size=original_task.image_size,
            tokens_spent=token_cost,
        )
        
        logger.info(
            f"Retry task {new_task.id} created from {task_id} "
            f"for user {callback.from_user.id}, cost: {token_cost} tokens"
        )
        
        # Enqueue for processing
        enqueue_generation_task(new_task.id)
        
        await callback.answer("Генерирую заново... ⏳", show_alert=False)
        
        # Update message to show retry initiated
        await callback.message.edit_reply_markup(reply_markup=None)
