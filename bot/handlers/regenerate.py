"""Handler for regenerate button callback."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository, TaskRepository
from bot.services.image_tokens import estimate_image_tokens
from bot.keyboards.inline import (
    CallbackData,
    image_settings_confirm_keyboard,
    main_menu_keyboard,
)
from bot.states.generation import GenerationStates, EditStates

logger = logging.getLogger(__name__)

router = Router(name="regenerate")


@router.callback_query(F.data.startswith(CallbackData.REGENERATE_PREFIX))
async def handle_regenerate(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Handle regenerate button click.
    
    Loads the original task settings and shows confirmation screen
    with the same prompt but editable settings.
    """
    # Extract task_id from callback data
    task_id_str = callback.data.replace(CallbackData.REGENERATE_PREFIX, "")
    
    try:
        task_id = int(task_id_str)
    except ValueError:
        await callback.answer("❌ Неверный ID задачи")
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        task_repo = TaskRepository(session)
        user_repo = UserRepository(session)
        
        # Get original task
        task = await task_repo.get_by_id(task_id)
        
        if task is None:
            await callback.answer("❌ Задача не найдена")
            return
        
        # Get user
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        
        if user is None:
            await callback.answer("❌ Пользователь не найден")
            return
        
        # Check if this task belongs to the user
        if task.user_id != user.id:
            await callback.answer("❌ Это не ваша задача")
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
            f"🔄 <b>Повторная генерация</b>\n\n"
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
            await callback.answer("❌ Исходное изображение не найдено")
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
            f"🔄 <b>Повторное редактирование</b>\n\n"
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
    await callback.answer()
