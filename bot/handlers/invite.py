"""Handler for /invite command - referral system."""

import logging

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository

logger = logging.getLogger(__name__)

router = Router(name="invite")


@router.message(Command("invite"))
async def cmd_invite(message: Message, bot: Bot) -> None:
    """Handle /invite command - show referral link and stats."""
    user_tg = message.from_user
    if user_tg is None:
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        
        if user is None:
            await message.answer("❌ Пользователь не найден. Используйте /start")
            return
        
        # Get referral stats
        stats = await user_repo.get_referral_stats(user.id)
        total_referrals = stats["total_referrals"]
    
    # Get bot username for referral link
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_tg.id}"
    
    text = (
        "👥 <b>Реферальная программа</b>\n\n"
        f"Ваша реферальная ссылка:\n"
        f"<code>{referral_link}</code>\n\n"
        f"📊 <b>Ваша статистика:</b>\n"
        f"• Приглашено пользователей: {total_referrals}\n\n"
        "💡 Делитесь ссылкой с друзьями!"
    )
    
    await message.answer(text)
