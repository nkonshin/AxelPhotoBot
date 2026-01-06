"""Handler for Guide (Гайд) - user instructions."""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.keyboards.inline import back_keyboard, CallbackData
from bot.utils.messages import GUIDE_TEXT
from bot.config import config

logger = logging.getLogger(__name__)

router = Router(name="guide")


@router.message(Command("guide"))
async def cmd_guide(message: Message) -> None:
    """Handle /guide command."""
    await message.answer(
        text=GUIDE_TEXT.format(support=config.support_username or "@support"),
        reply_markup=back_keyboard(),
    )


@router.callback_query(F.data == CallbackData.GUIDE)
async def show_guide(callback: CallbackQuery) -> None:
    """Handle 'Гайд' button from menu."""
    await callback.message.edit_text(
        text=GUIDE_TEXT.format(support=config.support_username or "@support"),
        reply_markup=back_keyboard(),
    )
    await callback.answer()

