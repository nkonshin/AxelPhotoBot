"""Handler for /start command and user registration."""

import logging
import re

from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository
from bot.keyboards.inline import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="start")


WELCOME_MESSAGE = """
🎨 <b>Добро пожаловать в AI Image Bot!</b>

Я помогу вам создавать уникальные изображения с помощью искусственного интеллекта.

<b>Что я умею:</b>
• 🎨 Создавать картинки по текстовому описанию
• ✏️ Редактировать ваши фотографии
• 💡 Предлагать готовые идеи для генерации

<b>Ваш баланс:</b> {tokens} 🪙

Выберите действие из меню ниже:
"""

WELCOME_BACK_MESSAGE = """
👋 <b>С возвращением!</b>

<b>Ваш баланс:</b> {tokens} 🪙

Выберите действие из меню:
"""


def parse_referral_code(args: str | None) -> int | None:
    """Parse referral code from /start arguments.
    
    Format: ref_USERID (e.g., ref_12345)
    Returns user ID or None if invalid.
    """
    if not args:
        return None
    
    match = re.match(r'^ref_(\d+)$', args)
    if match:
        return int(match.group(1))
    return None


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject) -> None:
    """
    Handle /start command.
    
    - Creates new user if not exists (with initial tokens)
    - Handles referral links (ref_USERID)
    - Shows welcome message with main menu
    - Clears any existing FSM state
    """
    # Clear any existing state
    await state.clear()
    
    user_tg = message.from_user
    if user_tg is None:
        return
    
    # Parse referral code from deep link
    referrer_telegram_id = parse_referral_code(command.args)
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        
        # Check if referrer exists (if referral code provided)
        referrer_id = None
        if referrer_telegram_id and referrer_telegram_id != user_tg.id:
            referrer = await user_repo.get_by_telegram_id(referrer_telegram_id)
            if referrer:
                referrer_id = referrer.id
        
        # Get or create user
        user, created = await user_repo.get_or_create(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name,
            referrer_id=referrer_id,
        )
        
        if created:
            logger.info(
                f"New user registered: {user_tg.id} (@{user_tg.username})"
                + (f" referred by {referrer_telegram_id}" if referrer_id else "")
            )
            text = WELCOME_MESSAGE.format(tokens=user.tokens)
        else:
            logger.info(
                f"Existing user started bot: {user_tg.id} (@{user_tg.username})"
            )
            text = WELCOME_BACK_MESSAGE.format(tokens=user.tokens)
    
    await message.answer(
        text=text,
        reply_markup=main_menu_keyboard(),
    )
