"""Handler for /support command."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import config

logger = logging.getLogger(__name__)

router = Router(name="support")


@router.message(Command("support"))
async def cmd_support(message: Message) -> None:
    """Handle /support command - show support contact."""
    if config.support_username:
        text = (
            "🆘 <b>Поддержка</b>\n\n"
            f"Если у вас возникли вопросы или проблемы, "
            f"напишите нам: {config.support_username}"
        )
    else:
        text = (
            "🆘 <b>Поддержка</b>\n\n"
            "К сожалению, контакт поддержки пока не настроен."
        )
    
    await message.answer(text)
