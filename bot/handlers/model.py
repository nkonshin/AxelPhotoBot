"""Handler for model selection."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository
from bot.keyboards.inline import model_keyboard, main_menu_keyboard, CallbackData

logger = logging.getLogger(__name__)

router = Router(name="model")


AVAILABLE_MODELS = {
    "gpt-image-1": {
        "name": "GPT-Image-1",
        "description": "Стандартная модель. Хорошее качество, быстрая генерация.",
    },
    "gpt-image-1.5": {
        "name": "GPT-Image-1.5", 
        "description": "Улучшенная модель. Лучшее качество, более детализированные изображения.",
    },
}


def get_model_info_text(current_model: str) -> str:
    """Generate model info text."""
    model_info = AVAILABLE_MODELS.get(current_model, AVAILABLE_MODELS["gpt-image-1"])
    return f"""
🤖 <b>Выбор модели</b>

Текущая модель: <b>{model_info['name']}</b>
{model_info['description']}

<i>Выберите модель для генерации изображений:</i>
"""


@router.callback_query(F.data == "model:gpt-image-1")
async def select_gpt_image_1(callback: CallbackQuery) -> None:
    """Handle GPT-Image-1 selection."""
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        
        if user is None:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        if user.selected_model == "gpt-image-1":
            await callback.answer("✅ GPT-Image-1 уже выбрана!", show_alert=False)
            return
        
        # Update user's selected model
        await user_repo.update_model(user.id, "gpt-image-1")
    
    await callback.message.edit_text(
        text=get_model_info_text("gpt-image-1"),
        reply_markup=model_keyboard("gpt-image-1"),
    )
    await callback.answer("✅ Модель GPT-Image-1 выбрана!")
    logger.info(f"User {user_tg.id} selected model gpt-image-1")


@router.callback_query(F.data == "model:gpt-image-1.5")
async def select_gpt_image_15(callback: CallbackQuery) -> None:
    """Handle GPT-Image-1.5 selection."""
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        
        if user is None:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        if user.selected_model == "gpt-image-1.5":
            await callback.answer("✅ GPT-Image-1.5 уже выбрана!", show_alert=False)
            return
        
        # Update user's selected model
        await user_repo.update_model(user.id, "gpt-image-1.5")
    
    await callback.message.edit_text(
        text=get_model_info_text("gpt-image-1.5"),
        reply_markup=model_keyboard("gpt-image-1.5"),
    )
    await callback.answer("✅ Модель GPT-Image-1.5 выбрана!")
    logger.info(f"User {user_tg.id} selected model gpt-image-1.5")


@router.callback_query(F.data == "model:coming_soon")
async def model_coming_soon(callback: CallbackQuery) -> None:
    """Handle 'coming soon' button click."""
    await callback.answer(
        "🚀 Новые модели скоро будут доступны!\n\n"
        "Следите за обновлениями.",
        show_alert=True,
    )
