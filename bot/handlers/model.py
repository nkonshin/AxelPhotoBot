"""Handler for model selection."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository
from bot.keyboards.inline import model_keyboard
from bot.services.image_tokens import convert_quality_for_model, is_valid_quality

logger = logging.getLogger(__name__)

router = Router(name="model")


AVAILABLE_MODELS = {
    "gpt-image-1": {
        "name": "GPT Image 1",
        "description": "Стандартная модель. Хорошее качество, поддержка генерации и редактирования.",
    },
    "gpt-image-1.5": {
        "name": "GPT Image 1.5",
        "description": "Улучшенная модель. Лучшее качество (только генерация, без редактирования).",
    },
    "seedream-4-5": {
        "name": "SeeDream 4.5",
        "description": "Новейшая модель BytePlus. Отличное качество, быстрая генерация и редактирование.",
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
    """Handle GPT Image 1 selection."""
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        
        if user is None:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        if user.selected_model == "gpt-image-1":
            await callback.answer("✅ GPT Image 1 уже выбрана!", show_alert=False)
            return
        
        await user_repo.update_model(user.id, "gpt-image-1")
    
    await callback.message.edit_text(
        text=get_model_info_text("gpt-image-1"),
        reply_markup=model_keyboard("gpt-image-1"),
    )
    await callback.answer("✅ Модель GPT Image 1 выбрана!")
    logger.info(f"User {user_tg.id} selected model gpt-image-1")


@router.callback_query(F.data == "model:gpt-image-1.5")
async def select_gpt_image_15(callback: CallbackQuery) -> None:
    """Handle GPT Image 1.5 selection."""
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        
        if user is None:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        if user.selected_model == "gpt-image-1.5":
            await callback.answer("✅ GPT Image 1.5 уже выбрана!", show_alert=False)
            return
        
        # Convert quality if switching from SeeDream
        new_quality = user.image_quality
        if not is_valid_quality(user.image_quality, "gpt-image-1.5"):
            new_quality = convert_quality_for_model(user.image_quality, "gpt-image-1.5")
            await user_repo.update_image_settings(user.id, image_quality=new_quality)
        
        await user_repo.update_model(user.id, "gpt-image-1.5")
    
    await callback.message.edit_text(
        text=get_model_info_text("gpt-image-1.5"),
        reply_markup=model_keyboard("gpt-image-1.5"),
    )
    await callback.answer("✅ Модель GPT Image 1.5 выбрана!")
    logger.info(f"User {user_tg.id} selected model gpt-image-1.5")


@router.callback_query(F.data == "model:seedream-4-5")
async def select_seedream_45(callback: CallbackQuery) -> None:
    """Handle SeeDream 4.5 selection."""
    user_tg = callback.from_user
    session_maker = get_session_maker()

    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)

        if user is None:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        if user.selected_model == "seedream-4-5":
            await callback.answer("✅ SeeDream 4.5 уже выбрана!", show_alert=False)
            return

        # Convert quality if switching from GPT models
        new_quality = user.image_quality
        if not is_valid_quality(user.image_quality, "seedream-4-5"):
            new_quality = convert_quality_for_model(user.image_quality, "seedream-4-5")
            await user_repo.update_image_settings(user.id, image_quality=new_quality)

        await user_repo.update_model(user.id, "seedream-4-5")

    await callback.message.edit_text(
        text=get_model_info_text("seedream-4-5"),
        reply_markup=model_keyboard("seedream-4-5"),
    )
    await callback.answer("✅ Модель SeeDream 4.5 выбрана!")
    logger.info(f"User {user_tg.id} selected model seedream-4-5")
