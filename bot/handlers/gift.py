"""Gift handlers - placeholder for future gift functionality.

This module provides a "coming soon" placeholder for the gift feature.
Full implementation will be added later with payment integration.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.keyboards.inline import CallbackData, back_keyboard

logger = logging.getLogger(__name__)

router = Router(name="gift")


@router.callback_query(F.data == CallbackData.GIFT)
async def handle_gift(callback: CallbackQuery) -> None:
    """Handle gift button click - show coming soon message."""
    
    text = (
        "🎁 <b>Подарить фотосессию</b>\n\n"
        "Эта функция скоро будет доступна!\n\n"
        "Вы сможете:\n"
        "• Выбрать пакет токенов для подарка\n"
        "• Указать получателя по @username\n"
        "• Добавить персональное сообщение\n\n"
        "🔔 Следите за обновлениями!"
    )
    
    await callback.message.edit_text(
        text=text,
        reply_markup=back_keyboard(),
    )
    await callback.answer()
