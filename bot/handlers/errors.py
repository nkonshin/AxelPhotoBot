"""Global error handler for the bot."""

import logging
from typing import Any

from aiogram import Router
from aiogram.types import Update, ErrorEvent
from aiogram.exceptions import TelegramAPIError

from bot.keyboards.inline import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="errors")


ERROR_MESSAGE = """
❌ <b>Произошла ошибка</b>

Что-то пошло не так. Пожалуйста, попробуйте позже.

Если ошибка повторяется, напишите в поддержку.
"""


@router.error()
async def global_error_handler(event: ErrorEvent) -> bool:
    """
    Global error handler for all unhandled exceptions.
    
    - Logs the error with context
    - Sends user-friendly message to the user
    - Returns True to mark error as handled
    """
    exception = event.exception
    update = event.update
    
    # Extract user info for logging
    user_id = None
    chat_id = None
    
    if update:
        if update.message:
            user_id = update.message.from_user.id if update.message.from_user else None
            chat_id = update.message.chat.id
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
            chat_id = update.callback_query.message.chat.id if update.callback_query.message else None
    
    # Log the error with context
    logger.error(
        f"Unhandled exception: {type(exception).__name__}: {exception}",
        extra={
            "user_id": user_id,
            "chat_id": chat_id,
            "update_type": type(update).__name__ if update else None,
        },
        exc_info=exception,
    )
    
    # Try to send error message to user
    if chat_id:
        try:
            from bot.bot import get_bot
            bot = get_bot()
            
            await bot.send_message(
                chat_id=chat_id,
                text=ERROR_MESSAGE,
                reply_markup=main_menu_keyboard(),
            )
        except TelegramAPIError as e:
            logger.error(f"Failed to send error message to user: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending error message: {e}")
    
    # Return True to mark error as handled
    return True


async def handle_unknown_command(message: Any) -> None:
    """
    Handle unknown commands by showing main menu.
    
    This is registered separately in the dispatcher.
    """
    await message.answer(
        text=(
            "🤔 Не понимаю эту команду.\n\n"
            "Выберите действие из меню:"
        ),
        reply_markup=main_menu_keyboard(),
    )
