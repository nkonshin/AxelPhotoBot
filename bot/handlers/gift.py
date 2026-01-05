"""Gift handlers for gifting tokens to other users.

Flow:
1. User clicks "🎁 Подарить фотосессию"
2. User selects a package
3. User enters recipient's @username
4. User pays via YooKassa
5. Gift is created with status "paid"
6. When recipient starts bot, gift is claimed and tokens are added
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import config
from bot.keyboards.inline import (
    CallbackData,
    SHOP_PACKAGES,
    back_keyboard,
    main_menu_keyboard,
)
from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository, GiftRepository, PaymentRepository
from bot.services.payment import PaymentService

logger = logging.getLogger(__name__)

router = Router(name="gift")


class GiftStates(StatesGroup):
    """FSM states for gift flow."""
    selecting_package = State()
    entering_username = State()
    confirming = State()


def gift_packages_keyboard():
    """Create keyboard with gift package options."""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    # Row 1: Starter + Small
    builder.row(
        InlineKeyboardButton(
            text="🐣 Starter (99₽)",
            callback_data="gift:package:starter",
        ),
        InlineKeyboardButton(
            text="✨ Small (249₽)",
            callback_data="gift:package:small",
        ),
    )
    
    # Row 2: Medium + Pro
    builder.row(
        InlineKeyboardButton(
            text="🔥 Medium (449₽)",
            callback_data="gift:package:medium",
        ),
        InlineKeyboardButton(
            text="😎 Pro (890₽)",
            callback_data="gift:package:pro",
        ),
    )
    
    # Row 3: VIP (full width)
    builder.row(
        InlineKeyboardButton(
            text="👑 Vip (1690₽)",
            callback_data="gift:package:vip",
        ),
    )
    
    # Back button
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data=CallbackData.BACK_TO_MENU,
        )
    )
    
    return builder.as_markup()


def gift_payment_keyboard(confirmation_url: str, gift_id: int):
    """Create keyboard with payment link for gift."""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💳 Оплатить подарок",
            url=confirmation_url,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Проверить оплату",
            callback_data=f"gift:check:{gift_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Отмена",
            callback_data=CallbackData.BACK_TO_MENU,
        )
    )
    
    return builder.as_markup()


@router.callback_query(F.data == CallbackData.GIFT)
async def handle_gift(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle gift button click - show package selection."""
    await state.clear()
    await state.set_state(GiftStates.selecting_package)
    
    text = (
        "🎁 <b>Подарить фотосессию</b>\n\n"
        "Выберите пакет токенов для подарка:\n\n"
        "🐣 <b>Starter</b> — 99 ₽ (10 токенов)\n"
        "✨ <b>Small</b> — 249 ₽ (50 токенов)\n"
        "🔥 <b>Medium</b> — 449 ₽ (120 токенов)\n"
        "😎 <b>Pro</b> — 890 ₽ (300 токенов)\n"
        "👑 <b>Vip</b> — 1690 ₽ (700 токенов)\n\n"
        "После оплаты получатель сможет использовать токены "
        "для генерации изображений 🎨"
    )
    
    await callback.message.edit_text(
        text=text,
        reply_markup=gift_packages_keyboard(),
    )
    await callback.answer()


@router.callback_query(GiftStates.selecting_package, F.data.startswith("gift:package:"))
async def select_gift_package(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle gift package selection."""
    package_key = callback.data.replace("gift:package:", "")
    
    if package_key not in SHOP_PACKAGES:
        await callback.answer("❌ Неизвестный пакет")
        return
    
    package = SHOP_PACKAGES[package_key]
    
    # Save package to state
    await state.update_data(package_key=package_key)
    await state.set_state(GiftStates.entering_username)
    
    await callback.message.edit_text(
        text=(
            f"🎁 <b>Подарок: {package['name']}</b>\n"
            f"💰 Стоимость: {package['price']} ₽\n"
            f"🪙 Токенов: {package['tokens']}\n\n"
            "Введите @username получателя подарка:\n\n"
            "<i>Например: @username</i>"
        ),
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@router.message(GiftStates.entering_username, F.text)
async def enter_recipient_username(message: Message, state: FSMContext) -> None:
    """Handle recipient username input."""
    username = message.text.strip()
    
    # Validate username format
    if not username.startswith("@"):
        await message.answer(
            "❌ Username должен начинаться с @\n\n"
            "Например: @username",
            reply_markup=back_keyboard(),
        )
        return
    
    # Remove @ for storage
    username_clean = username.lstrip("@")
    
    if len(username_clean) < 3:
        await message.answer(
            "❌ Username слишком короткий\n\n"
            "Введите корректный @username",
            reply_markup=back_keyboard(),
        )
        return
    
    # Check if user is trying to gift to themselves
    if message.from_user.username and username_clean.lower() == message.from_user.username.lower():
        await message.answer(
            "❌ Нельзя подарить токены самому себе!\n\n"
            "Введите @username другого пользователя",
            reply_markup=back_keyboard(),
        )
        return
    
    # Check if YooKassa is configured
    if not PaymentService.is_configured():
        await message.answer(
            "💳 Оплата подарков скоро будет доступна!",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return
    
    # Get package from state
    data = await state.get_data()
    package_key = data.get("package_key")
    
    if not package_key or package_key not in SHOP_PACKAGES:
        await message.answer(
            "❌ Ошибка: пакет не выбран. Попробуйте снова.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return
    
    package = SHOP_PACKAGES[package_key]
    
    # Get sender user
    user_tg = message.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        gift_repo = GiftRepository(session)
        
        sender = await user_repo.get_by_telegram_id(user_tg.id)
        if not sender:
            await message.answer(
                "❌ Пользователь не найден. Используйте /start",
                reply_markup=back_keyboard(),
            )
            await state.clear()
            return
        
        # Check if recipient exists (optional - we allow gifts to non-registered users)
        recipient = await user_repo.get_by_username(username_clean)
        recipient_status = "уже в боте ✅" if recipient else "получит при первом входе 📩"
        
        # Create gift record (pending payment)
        gift = await gift_repo.create(
            sender_id=sender.id,
            recipient_username=username_clean,
            package=package_key,
            tokens_amount=package["tokens"],
            status="pending",
        )
        
        # Create payment for gift
        payment_data = PaymentService.create_gift_payment(
            user_id=sender.id,
            telegram_id=user_tg.id,
            package_key=package_key,
            gift_id=gift.id,
            recipient_username=username_clean,
        )
        
        if not payment_data:
            await message.answer(
                "❌ Ошибка создания платежа. Попробуйте позже.",
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            return
        
        # Save payment to database
        payment_repo = PaymentRepository(session)
        payment = await payment_repo.create(
            user_id=sender.id,
            yookassa_payment_id=payment_data["payment_id"],
            package=package_key,
            tokens_amount=package["tokens"],
            amount_value=payment_data["amount"],
            confirmation_url=payment_data["confirmation_url"],
            status=payment_data["status"],
        )
        
        # Update payment with gift info
        payment.is_gift = True
        payment.gift_recipient_username = username_clean
        
        # Update gift with payment_id
        gift.payment_id = payment.id
        await session.commit()
    
    await state.clear()
    
    # Show payment message
    await message.answer(
        text=(
            f"🎁 <b>Подарок для @{username_clean}</b>\n\n"
            f"<b>Пакет:</b> {package['name']}\n"
            f"<b>Токенов:</b> {package['tokens']} 🪙\n"
            f"<b>Сумма:</b> {package['price']} ₽\n\n"
            f"<b>Получатель:</b> @{username_clean}\n"
            f"<i>Статус: {recipient_status}</i>\n\n"
            "Нажмите «Оплатить подарок» для перехода на страницу оплаты.\n\n"
            "После оплаты получатель автоматически получит токены! 🎉"
        ),
        reply_markup=gift_payment_keyboard(payment_data["confirmation_url"], gift.id),
    )


@router.callback_query(F.data.startswith("gift:check:"))
async def check_gift_payment(callback: CallbackQuery) -> None:
    """Check gift payment status."""
    gift_id = int(callback.data.replace("gift:check:", ""))
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        gift_repo = GiftRepository(session)
        user_repo = UserRepository(session)
        payment_repo = PaymentRepository(session)
        
        gift = await gift_repo.get_by_id(gift_id)
        
        if not gift:
            await callback.answer("❌ Подарок не найден")
            return
        
        if not gift.payment_id:
            await callback.answer("❌ Платёж не найден")
            return
        
        # Get payment
        from bot.db.models import Payment
        result = await session.execute(
            select(Payment).where(Payment.id == gift.payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            await callback.answer("❌ Платёж не найден")
            return
        
        # Check status in YooKassa
        yookassa_payment = PaymentService.get_payment(payment.yookassa_payment_id)
        
        if not yookassa_payment:
            await callback.answer("❌ Ошибка проверки статуса")
            return
        
        old_status = payment.status
        payment.status = yookassa_payment.status
        payment.paid = yookassa_payment.paid
        
        if yookassa_payment.status == "succeeded" and yookassa_payment.paid:
            if old_status != "succeeded":
                # Mark gift as paid (waiting for recipient to claim)
                gift.status = "paid"
                
                # Check if recipient already exists
                recipient = await user_repo.get_by_username(gift.recipient_username)
                
                if recipient:
                    # Recipient exists - add tokens immediately
                    await user_repo.update_tokens(recipient.id, gift.tokens_amount)
                    gift.status = "claimed"
                    gift.recipient_id = recipient.id
                    
                    logger.info(
                        f"Gift {gift.id} claimed immediately: "
                        f"{gift.tokens_amount} tokens to @{gift.recipient_username}"
                    )
                    
                    # Notify recipient
                    try:
                        from bot.bot import get_bot
                        bot = get_bot()
                        sender = await user_repo.get_by_id(gift.sender_id)
                        sender_name = f"@{sender.username}" if sender and sender.username else "друга"
                        
                        await bot.send_message(
                            chat_id=recipient.telegram_id,
                            text=(
                                f"🎁 <b>Вам подарили токены!</b>\n\n"
                                f"<b>От:</b> {sender_name}\n"
                                f"<b>Пакет:</b> {SHOP_PACKAGES.get(gift.package, {}).get('name', gift.package)}\n"
                                f"<b>Токенов:</b> +{gift.tokens_amount} 🪙\n\n"
                                "Токены уже на вашем балансе! 🎉"
                            ),
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify gift recipient: {e}")
                
                await session.commit()
            
            package = SHOP_PACKAGES.get(gift.package, {})
            status_text = "уже получил токены! 🎉" if gift.status == "claimed" else "получит токены при входе в бота 📩"
            
            await callback.message.edit_text(
                text=(
                    "✅ <b>Подарок оплачен!</b>\n\n"
                    f"<b>Пакет:</b> {package.get('name', gift.package)}\n"
                    f"<b>Токенов:</b> {gift.tokens_amount} 🪙\n"
                    f"<b>Получатель:</b> @{gift.recipient_username}\n\n"
                    f"<i>Статус: {status_text}</i>\n\n"
                    "Спасибо за подарок! 💝"
                ),
                reply_markup=main_menu_keyboard(),
            )
            await callback.answer("✅ Подарок оплачен!")
            
        elif yookassa_payment.status == "canceled":
            gift.status = "canceled"
            await session.commit()
            
            await callback.message.edit_text(
                text=(
                    "❌ <b>Платёж отменён</b>\n\n"
                    "Платёж был отменён или истёк срок оплаты.\n"
                    "Попробуйте создать новый подарок."
                ),
                reply_markup=main_menu_keyboard(),
            )
            await callback.answer("Платёж отменён")
            
        elif yookassa_payment.status == "pending":
            await session.commit()
            await callback.answer(
                "⏳ Платёж ещё обрабатывается. Подождите немного.",
                show_alert=True,
            )
        else:
            await session.commit()
            await callback.answer(f"Статус: {yookassa_payment.status}")


# Import for select
from sqlalchemy import select
