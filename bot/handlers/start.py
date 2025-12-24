"""Handler for /start command and user registration."""

import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
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


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    Handle /start command.
    
    - Creates new user if not exists (with initial tokens)
    - Shows welcome message with main menu
    - Clears any existing FSM state
    """
    # Clear any existing state
    await state.clear()
    
    user_tg = message.from_user
    if user_tg is None:
        return
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        
        # Get or create user
        user, created = await user_repo.get_or_create(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name,
        )
        
        if created:
            logger.info(
                f"New user registered: {user_tg.id} (@{user_tg.username})"
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
