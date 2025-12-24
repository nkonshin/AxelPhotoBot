"""Handler for model selection."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.keyboards.inline import model_keyboard, main_menu_keyboard, CallbackData

logger = logging.getLogger(__name__)

router = Router(name="model")


MODEL_INFO = """
🤖 <b>Выбор модели</b>

Текущая модель для генерации изображений:

✅ <b>GPT-Image-1</b>
Высокое качество, отличная детализация, понимание сложных промптов.

<i>Стоимость: 1 токен за генерацию</i>
"""


# Note: Main model menu is handled in menu.py
# This router handles additional model-related callbacks


@router.callback_query(F.data == "model:gpt-image-1")
async def select_gpt_image(callback: CallbackQuery) -> None:
    """Handle GPT-Image-1 selection (already selected)."""
    await callback.answer(
        "✅ GPT-Image-1 уже выбрана!",
        show_alert=False,
    )


@router.callback_query(F.data == "model:coming_soon")
async def model_coming_soon(callback: CallbackQuery) -> None:
    """Handle 'coming soon' button click."""
    await callback.answer(
        "🚀 Новые модели скоро будут доступны!\n\n"
        "Следите за обновлениями.",
        show_alert=True,
    )
