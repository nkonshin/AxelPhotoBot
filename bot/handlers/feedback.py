"""Feedback handlers for generation results.

Handles user feedback (👍/👎) and retry functionality.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.db.database import get_session_maker
from bot.db.repositories import TaskRepository, UserRepository
from bot.keyboards.inline import (
    CallbackData,
    image_settings_confirm_keyboard,
)
from bot.services.image_tokens import estimate_image_tokens
from bot.states.generation import GenerationStates, EditStates

logger = logging.getLogger(__name__)

router = Router(name="feedback")


@router.callback_query(F.data.startswith(CallbackData.FEEDBACK_POSITIVE_PREFIX))
async def handle_positive_feedback(callback: CallbackQuery) -> None:
    """Handle positive feedback (👍) - just acknowledge."""
    task_id = int(callback.data.replace(CallbackData.FEEDBACK_POSITIVE_PREFIX, ""))
    
    logger.info(f"Positive feedback for task {task_id} from user {callback.from_user.id}")
    
    await callback.answer("Спасибо за отзыв! 🙏", show_alert=False)


@router.callback_query(F.data.startswith(CallbackData.FEEDBACK_NEGATIVE_PREFIX))
async def handle_negative_feedback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle negative feedback (👎) - show settings menu like regenerate button."""
    task_id = int(callback.data.replace(CallbackData.FEEDBACK_NEGATIVE_PREFIX, ""))
    
    logger.info(f"Negative feedback for task {task_id} from user {callback.from_user.id}")
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        task_repo = TaskRepository(session)
        user_repo = UserRepository(session)
        
        # Get original task
        task = await task_repo.get_by_id(task_id)
        
        if task is None:
            await callback.answer("❌ Задача не найдена", show_alert=True)
            return
        
        # Get user
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        
        if user is None:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        # Check if this task belongs to the user
        if task.user_id != user.id:
            await callback.answer("❌ Это не ваша задача", show_alert=True)
            return
        
        balance = user.tokens
        quality = task.image_quality
        size = task.image_size
        model = task.model
        prompt = task.prompt
    
    cost = estimate_image_tokens(quality, size)
    
    # Determine if it's a generate or edit task
    if task.task_type == "generate":
        # Save to state for generation flow
        await state.update_data(
            prompt=prompt,
            user_id=user.id,
            image_quality=quality,
            image_size=size,
            model=model,
            expensive_confirmed=False,
        )
        await state.set_state(GenerationStates.confirm_generation)
        
        prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
        
        text = (
            f"😔 <b>Жаль, что не понравилось</b>\n\n"
            f"Попробуйте изменить настройки:\n\n"
            f"<b>Ваш промпт:</b>\n<i>{prompt_preview}</i>\n\n"
            f"<b>Модель:</b> {model}\n"
            f"<b>Качество:</b> {quality}\n"
            f"<b>Формат:</b> {size}\n\n"
            f"<b>Стоимость:</b> {cost} 🪙\n"
            f"<b>Ваш баланс:</b> {balance} 🪙\n"
            f"<b>После генерации:</b> {balance - cost} 🪙\n\n"
            f"Подтвердить генерацию?"
        )
    else:
        # Edit task - need source image
        source_file_id = task.source_image_url
        
        if not source_file_id:
            await callback.answer("❌ Исходное изображение не найдено", show_alert=True)
            return
        
        await state.update_data(
            prompt=prompt,
            user_id=user.id,
            source_file_id=source_file_id,
            image_quality=quality,
            image_size=size,
            model=model,
            expensive_confirmed=False,
        )
        await state.set_state(EditStates.confirm_edit)
        
        prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
        
        text = (
            f"😔 <b>Жаль, что не понравилось</b>\n\n"
            f"Попробуйте изменить настройки:\n\n"
            f"<b>Описание изменений:</b>\n<i>{prompt_preview}</i>\n\n"
            f"<b>Модель:</b> {model}\n"
            f"<b>Качество:</b> {quality}\n"
            f"<b>Формат:</b> {size}\n\n"
            f"<b>Стоимость:</b> {cost} 🪙\n"
            f"<b>Ваш баланс:</b> {balance} 🪙\n"
            f"<b>После редактирования:</b> {balance - cost} 🪙\n\n"
            f"Подтвердить редактирование?"
        )
    
    await callback.message.answer(
        text=text,
        reply_markup=image_settings_confirm_keyboard(quality, size),
    )
    await callback.answer("Жаль, что не понравилось 😔", show_alert=False)
