"""Handler for user profile (Личный кабинет)."""

import logging

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
from bot.utils.messages import (
    PROFILE_HEADER,
    PROFILE_HISTORY_ITEM,
    PROFILE_NO_HISTORY,
    PROFILE_IMAGE_CAPTION,
    ERROR_USER_NOT_FOUND,
    ERROR_TASK_NOT_FOUND,
    ERROR_IMAGE_UNAVAILABLE,
    ERROR_IMAGE_LOAD_FAILED,
    format_task_status,
    format_task_type,
    format_date,
)

logger = logging.getLogger(__name__)

router = Router(name="profile")


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
                ERROR_USER_NOT_FOUND,
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
    text = PROFILE_HEADER.format(
        user_name=user.username or user.first_name or "Пользователь",
        tokens=user.tokens,
        total=total_generations,
        model=user.selected_model,
        quality=quality_label,
        size=user.image_size,
    )
    
    if history:
        for i, task in enumerate(history[:3], 1):
            status_icon = format_task_status(task.status)
            task_type_str = format_task_type(task.task_type)
            date = format_date(task.created_at)
            
            # Truncate prompt for display
            prompt_preview = task.prompt[:30] + "..." if len(task.prompt) > 30 else task.prompt
            
            text += PROFILE_HISTORY_ITEM.format(
                index=i,
                task_type=task_type_str,
                status=status_icon,
                date=date,
                prompt=prompt_preview,
            )
    else:
        text += PROFILE_NO_HISTORY

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
        await callback.answer(ERROR_TASK_NOT_FOUND)
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        task_repo = TaskRepository(session)
        task = await task_repo.get_by_id(task_id)
        
        if task is None:
            await callback.answer(ERROR_TASK_NOT_FOUND)
            return
        
        if task.status != "done":
            await callback.answer(ERROR_IMAGE_UNAVAILABLE)
            return
    
    # Send the image
    try:
        caption = PROFILE_IMAGE_CAPTION.format(
            prompt=task.prompt[:200] + ('...' if len(task.prompt) > 200 else ''),
            quality=task.image_quality,
            size=task.image_size,
            date=format_date(task.created_at),
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
            await callback.answer(ERROR_IMAGE_UNAVAILABLE)
            return

        await callback.answer()
    except Exception as e:
        logger.error(f"Failed to send history image: {e}")
        await callback.answer(ERROR_IMAGE_LOAD_FAILED)


@router.callback_query(F.data == "history:back")
async def back_to_profile(callback: CallbackQuery) -> None:
    """Go back to profile from history item."""
    # Re-show profile
    await show_profile(callback)
