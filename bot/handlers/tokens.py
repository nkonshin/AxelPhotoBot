"""Handler for token purchase (Купить токены)."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository
from bot.keyboards.inline import tokens_keyboard, CallbackData

logger = logging.getLogger(__name__)

router = Router(name="tokens")


TOKENS_MESSAGE = """
💰 <b>Купить токены</b>

Ваш текущий баланс: <b>{balance}</b> 🪙

<b>Доступные пакеты:</b>

📦 <b>Стартовый</b> — 50 токенов
   💵 99 ₽

📦 <b>Оптимальный</b> — 150 токенов
   💵 249 ₽ <i>(экономия 17%)</i>

📦 <b>Профессиональный</b> — 500 токенов
   💵 699 ₽ <i>(экономия 30%)</i>

🔜 <i>Оплата скоро будет доступна</i>
"""


# Note: Main tokens menu is handled in menu.py
# This router handles additional token-related callbacks


@router.callback_query(F.data == "tokens:coming_soon")
async def tokens_coming_soon(callback: CallbackQuery) -> None:
    """Handle 'coming soon' button click."""
    await callback.answer(
        "💳 Оплата скоро будет доступна!\n\n"
        "Мы работаем над интеграцией платежей.",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("tokens:buy:"))
async def buy_tokens(callback: CallbackQuery) -> None:
    """Handle token purchase (placeholder)."""
    # Extract package from callback data
    package = callback.data.split(":")[-1]
    
    await callback.answer(
        f"💳 Покупка пакета «{package}» скоро будет доступна!",
        show_alert=True,
    )
