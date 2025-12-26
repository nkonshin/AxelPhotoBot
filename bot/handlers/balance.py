"""Handler for balance commands."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository
from bot.keyboards.inline import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="balance")


@router.message(Command("balance"))
@router.message(Command("tokens"))
async def cmd_balance(message: Message) -> None:
    """Show current user balance and settings."""

    user_tg = message.from_user
    if user_tg is None:
        return

    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)

    if user is None:
        await message.answer(
            text="❌ Пользователь не найден. Используйте /start",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        text=(
            "👛 <b>Баланс</b>\n\n"
            f"<b>Токены:</b> {user.tokens} 🪙\n\n"
            f"<b>Модель:</b> {user.selected_model}\n"
            f"<b>Качество:</b> {user.image_quality}\n"
            f"<b>Формат:</b> {user.image_size}\n"
        ),
        reply_markup=main_menu_keyboard(),
    )
