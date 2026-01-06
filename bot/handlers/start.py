"""Handler for /start command and user registration."""

import logging
import re

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository
from bot.keyboards.inline import main_menu_keyboard, subscription_keyboard
from bot.utils.messages import (
    WELCOME_MESSAGE,
    LOW_BALANCE_WARNING,
    SUBSCRIPTION_MESSAGE,
    SUBSCRIPTION_SUCCESS,
    CALLBACK_SUBSCRIPTION_NOT_CONFIRMED,
    CALLBACK_SUBSCRIPTION_CONFIRMED,
)

logger = logging.getLogger(__name__)

router = Router(name="start")


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


async def check_subscription(bot: Bot, user_id: int, channel: str) -> bool:
    """Check if user is subscribed to channel.
    
    Args:
        bot: Bot instance
        user_id: Telegram user ID
        channel: Channel username (e.g., @nkonshin_ai)
    
    Returns:
        True if subscribed or on error (fail-open), False if not subscribed
    """
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Failed to check subscription for user {user_id}: {e}")
        # Fail-open: if we can't check, allow access
        return True


async def get_subscription_required() -> bool:
    """Get subscription requirement status from Redis.
    
    Returns config default if Redis is not available.
    """
    try:
        import redis.asyncio as redis
        r = redis.from_url(config.redis_url)
        value = await r.get("subscription_required")
        await r.close()
        if value is None:
            return config.subscription_required
        return value.decode() == "true"
    except Exception as e:
        logger.error(f"Failed to get subscription_required from Redis: {e}")
        return config.subscription_required


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject, bot: Bot) -> None:
    """Handle /start command."""
    await state.clear()
    
    user_tg = message.from_user
    if user_tg is None:
        return
    
    referrer_telegram_id = parse_referral_code(command.args)
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        
        existing_user = await user_repo.get_by_telegram_id(user_tg.id)
        is_new_user = existing_user is None
        
        # Send welcome video for ALL users on every /start
        # Send BEFORE text message to ensure correct order
        if config.welcome_video_file_id:
            import asyncio
            try:
                # Try to send as video with 5 second timeout
                await asyncio.wait_for(
                    message.answer_video(video=config.welcome_video_file_id),
                    timeout=5.0
                )
                logger.info(f"Welcome video sent to user {user_tg.id}")
            except asyncio.TimeoutError:
                logger.warning(f"Welcome video timeout for user {user_tg.id} - Telegram API slow, continuing...")
            except Exception as e:
                logger.error(f"Failed to send welcome video to {user_tg.id}: {e}")
        
        if is_new_user:
            # Check subscription requirement
            subscription_required = await get_subscription_required()
            
            if subscription_required and config.subscription_channel:
                is_subscribed = await check_subscription(
                    bot, user_tg.id, config.subscription_channel
                )
                
                if not is_subscribed:
                    await message.answer(
                        text=SUBSCRIPTION_MESSAGE.format(channel=config.subscription_channel),
                        reply_markup=subscription_keyboard(config.subscription_channel),
                    )
                    return
            
            # Check for pending gifts
            from bot.db.repositories import GiftRepository
            gift_repo = GiftRepository(session)
            pending_gifts = await gift_repo.get_pending_gifts_for_username(user_tg.username)
        
        referrer_id = None
        if referrer_telegram_id and referrer_telegram_id != user_tg.id:
            referrer = await user_repo.get_by_telegram_id(referrer_telegram_id)
            if referrer:
                referrer_id = referrer.id
        
        user, created = await user_repo.get_or_create(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name,
            referrer_id=referrer_id,
        )
        
        # Process pending gifts for new users
        gift_message = ""
        if is_new_user and user_tg.username:
            from bot.db.repositories import GiftRepository, TransactionRepository
            gift_repo = GiftRepository(session)
            tx_repo = TransactionRepository(session)
            pending_gifts = await gift_repo.get_pending_gifts_for_username(user_tg.username)
            
            total_gift_tokens = 0
            gift_senders = []
            for gift in pending_gifts:
                total_gift_tokens += gift.tokens_amount
                # Get sender info
                sender = await user_repo.get_by_id(gift.sender_id)
                sender_name = f"@{sender.username}" if sender and sender.username else "Аноним"
                if sender:
                    gift_senders.append(sender_name)
                # Mark gift as claimed
                gift.recipient_id = user.id
                gift.status = "claimed"
                
                # Create transaction for this gift
                await tx_repo.create(
                    user_id=user.id,
                    type="gift_received",
                    tokens_amount=gift.tokens_amount,
                    description=f"Подарок от {sender_name}",
                    gift_id=gift.id,
                    related_user_id=sender.id if sender else None,
                )
            
            if total_gift_tokens > 0:
                await user_repo.update_tokens(user.id, total_gift_tokens)
                user.tokens += total_gift_tokens
                await session.commit()
                
                senders_text = ", ".join(gift_senders) if gift_senders else "друга"
                gift_message = f"\n\n🎁 <b>Вам подарили {total_gift_tokens} токенов от {senders_text}!</b>"
        
        # Build welcome message with new format
        user_name = user_tg.first_name or user_tg.username or "друг"
        balance = user.tokens
        max_generations = balance // 2  # Low quality = 2 tokens
        
        # Show low balance warning if 3 or fewer tokens (and no gift message)
        low_balance_warning = ""
        if balance <= 3 and not gift_message:
            low_balance_warning = "\n" + LOW_BALANCE_WARNING
        
        text = WELCOME_MESSAGE.format(
            user_name=user_name,
            balance=balance,
            max_generations=max_generations,
            gift_message=gift_message,
            low_balance_warning=low_balance_warning,
        )
        
        if created:
            logger.info(
                f"New user registered: {user_tg.id} (@{user_tg.username})"
                + (f" referred by {referrer_telegram_id}" if referrer_id else "")
            )
        else:
            logger.info(
                f"Existing user started bot: {user_tg.id} (@{user_tg.username})"
            )
    
    await message.answer(
        text=text,
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot) -> None:
    """Handle subscription check button click."""
    # Answer callback immediately to prevent timeout
    await callback.answer()
    
    user_tg = callback.from_user
    
    is_subscribed = await check_subscription(
        bot, user_tg.id, config.subscription_channel
    )
    
    if not is_subscribed:
        await callback.message.answer(
            text=CALLBACK_SUBSCRIPTION_NOT_CONFIRMED,
        )
        return
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        
        user, created = await user_repo.get_or_create(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name,
        )
        
        if created:
            logger.info(f"New user registered after subscription: {user_tg.id}")
    
    await callback.message.edit_text(
        text=SUBSCRIPTION_SUCCESS.format(tokens=user.tokens),
        reply_markup=main_menu_keyboard(),
    )
