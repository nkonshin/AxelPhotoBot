"""Handler for user profile (Личный кабинет)."""

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository, TaskRepository
from bot.keyboards.inline import (
    CallbackData,
    main_menu_keyboard,
)
from bot.services.image_tokens import IMAGE_QUALITY_LABELS

logger = logging.getLogger(__name__)

router = Router(name="profile")


def format_task_status(status: str) -> str:
    """Format task status for display."""
    status_map = {
        "pending": "⏳ В очереди",
        "processing": "🔄 Обработка",
        "done": "✅ Готово",
        "failed": "❌ Ошибка",
    }
    return status_map.get(status, status)


def format_task_type(task_type: str) -> str:
    """Format task type for display."""
    type_map = {
        "generate": "🎨 Генерация",
        "edit": "🪄 Редактирование",
    }
    return type_map.get(task_type, task_type)


def format_date(dt: datetime) -> str:
    """Format datetime for display."""
    if dt is None:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


@router.callback_query(F.data == CallbackData.PROFILE)
async def show_profile(callback: CallbackQuery) -> None:
    """Show user profile with balance and statistics."""
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        
        user = await user_repo.get_by_telegram_id(user_tg.id)
        
        if user is None:
            await callback.message.edit_text(
                "❌ Пользователь не найден. Используйте /start",
                reply_markup=main_menu_keyboard(),
            )
            await callback.answer()
            return
        
        # Get user's generation history (only 3 most recent)
        history = await task_repo.get_user_history(user.id, limit=3)
        
        # Get total count for stats (separate query)
        all_history = await task_repo.get_user_history(user.id, limit=100)
        total_generations = len(all_history)
        successful_generations = sum(1 for t in all_history if t.status == "done")
    
    # Format quality label
    quality_label = IMAGE_QUALITY_LABELS.get(user.image_quality, user.image_quality)
    
    # Build profile message
    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"<b>Баланс:</b> {user.tokens} 🪙\n"
        f"<b>Всего генераций:</b> {total_generations}\n"
        f"<b>Успешных:</b> {successful_generations}\n"
        f"<b>Модель:</b> {user.selected_model}\n"
        f"<b>Качество:</b> {quality_label}\n"
        f"<b>Формат:</b> {user.image_size}\n\n"
    )
    
    if history:
        text += "<b>📋 Последние генерации:</b>\n\n"
        for i, task in enumerate(history[:3], 1):
            status_icon = format_task_status(task.status)
            task_type = format_task_type(task.task_type)
            date = format_date(task.created_at)
            
            # Truncate prompt for display
            prompt_preview = task.prompt[:30] + "..." if len(task.prompt) > 30 else task.prompt
            
            text += (
                f"{i}. {task_type}\n"
                f"   {status_icon} | {date}\n"
                f"   <i>{prompt_preview}</i>\n\n"
            )
    else:
        text += (
            "<i>У вас пока нет генераций.</i>\n\n"
            "Создайте первое изображение в разделе «Создать картинку с нуля»!"
        )

    # Only back button, no history image buttons
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data=CallbackData.BACK_TO_MENU,
        )
    )

    await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("history:show:"))
async def show_history_image(callback: CallbackQuery) -> None:
    """Show image from history item."""
    # Extract task_id from callback data
    try:
        task_id = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID задачи")
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        task_repo = TaskRepository(session)
        task = await task_repo.get_by_id(task_id)
        
        if task is None:
            await callback.answer("❌ Задача не найдена")
            return
        
        if task.status != "done":
            await callback.answer("❌ Изображение недоступно")
            return
    
    # Send the image
    try:
        caption = (
            f"🖼 <b>Результат</b>\n\n"
            f"<b>Промпт:</b> <i>{task.prompt[:200]}{'...' if len(task.prompt) > 200 else ''}</i>\n"
            f"<b>Качество:</b> {task.image_quality}\n"
            f"<b>Формат:</b> {task.image_size}\n"
            f"<b>Дата:</b> {format_date(task.created_at)}"
        )

        if task.result_file_id:
            await callback.message.answer_document(
                document=task.result_file_id,
                caption=caption,
            )
        elif task.result_image_url:
            await callback.message.answer_document(
                document=task.result_image_url,
                caption=caption,
            )
        else:
            await callback.answer("❌ Изображение недоступно")
            return

        await callback.answer()
    except Exception as e:
        logger.error(f"Failed to send history image: {e}")
        await callback.answer("❌ Не удалось загрузить изображение")


@router.callback_query(F.data == "history:back")
async def back_to_profile(callback: CallbackQuery) -> None:
    """Go back to profile from history item."""
    # Re-show profile
    await show_profile(callback)
